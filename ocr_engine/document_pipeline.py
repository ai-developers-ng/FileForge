"""Document conversion pipeline using Pandoc via pypandoc."""

import glob
import json
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Optional

import pypandoc

from .storage import document_result_path

logger = logging.getLogger(__name__)

# Common TeX binary directories not always in PATH
_STATIC_TEX_SEARCH_PATHS = [
    "/Library/TeX/texbin",  # macOS BasicTeX / MacTeX
]


def _candidate_tex_paths():
    """Build a de-duplicated list of likely TeX bin directories."""
    dynamic_paths = []
    dynamic_paths.extend(glob.glob("/usr/local/texlive/*/bin/*"))
    dynamic_paths.extend(glob.glob("/usr/local/texlive/*basic/bin/*"))

    # Keep insertion order while removing duplicates
    candidates = []
    for path in [*_STATIC_TEX_SEARCH_PATHS, *dynamic_paths]:
        if path not in candidates:
            candidates.append(path)
    return candidates


def _ensure_tex_in_path():
    """Add TeX directories to PATH so pdflatex and its helpers are found."""
    current_path = os.environ.get("PATH", "")
    path_entries = current_path.split(os.pathsep) if current_path else []
    dirs_to_add = [
        path
        for path in _candidate_tex_paths()
        if os.path.isdir(path) and path not in path_entries
    ]
    if dirs_to_add:
        os.environ["PATH"] = os.pathsep.join(dirs_to_add + path_entries)
        logger.info(f"Added TeX directories to PATH: {dirs_to_add}")


@dataclass
class DocumentConversionOptions:
    """Options for document conversion."""

    output_format: str = "pdf"


# Input format mapping (file extension to pandoc format)
INPUT_FORMAT_MAP = {
    ".docx": "docx",
    ".doc": "doc",
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".rtf": "rtf",
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".rst": "rst",
    ".epub": "epub",
    ".odt": "odt",
    ".docbook": "docbook",
    ".xml": "docbook",
    # Pandoc no longer supports "plain" as an input reader in newer versions.
    ".txt": "markdown",
}

# Output format mapping (user-friendly name to pandoc format)
OUTPUT_FORMAT_MAP = {
    "pdf": "pdf",
    "docx": "docx",
    "html": "html",
    "txt": "plain",
    "md": "markdown",
}

# File extensions for output formats
OUTPUT_EXTENSIONS = {
    "pdf": "pdf",
    "docx": "docx",
    "html": "html",
    "txt": "txt",
    "md": "md",
}


def process_document_job(job_id, file_path, options, settings, job_store):
    """Process a document conversion job using Pandoc.

    Args:
        job_id: Unique job identifier
        file_path: Path to the uploaded document file
        options: Dictionary with conversion options
        settings: Application settings
        job_store: JobStore instance for status updates
    """
    job_store.update_job(job_id, status="running", progress=0)

    result = {
        "job_id": job_id,
        "original_file": os.path.basename(file_path),
        "options": options,
        "errors": [],
    }

    try:
        # Parse options
        conv_options = DocumentConversionOptions(
            output_format=options.get("output_format", "pdf"),
        )

        job_store.update_job(job_id, progress=10)

        # Detect input format from file extension
        ext = os.path.splitext(file_path)[1].lower()
        input_format = INPUT_FORMAT_MAP.get(ext)

        if not input_format:
            raise ValueError(f"Unsupported input format: {ext}")

        result["input_format"] = input_format
        result["output_format"] = conv_options.output_format

        job_store.update_job(job_id, progress=20)

        # Determine output format for pandoc
        pandoc_output_format = OUTPUT_FORMAT_MAP.get(conv_options.output_format)
        if not pandoc_output_format:
            raise ValueError(f"Unsupported output format: {conv_options.output_format}")

        # Generate output path
        output_ext = OUTPUT_EXTENSIONS.get(conv_options.output_format, conv_options.output_format)
        output_path = document_result_path(settings.result_dir, job_id, output_ext)

        job_store.update_job(job_id, progress=30)

        # Perform conversion with pandoc
        logger.info(f"Converting {file_path} from {input_format} to {pandoc_output_format}")

        # Perform conversion
        if pandoc_output_format == "pdf":
            # Ensure TeX binaries (pdflatex, kpsewhich, etc.) are on PATH
            _ensure_tex_in_path()

            # Try PDF engines in order of preference
            pdf_engine_names = ["pdflatex", "xelatex", "lualatex", "weasyprint", "wkhtmltopdf", "typst"]
            discovered_engines = [(name, shutil.which(name)) for name in pdf_engine_names]
            available_engines = [(name, path) for name, path in discovered_engines if path]

            if not available_engines:
                raise RuntimeError(
                    "No PDF engine available. Install one of: "
                    f"{', '.join(pdf_engine_names)}. "
                    "On macOS: brew install basictex. "
                    "On Debian/Ubuntu: apt-get install texlive-latex-base"
                )

            last_err = None
            for engine_name, engine_path in available_engines:
                try:
                    pypandoc.convert_file(
                        file_path,
                        pandoc_output_format,
                        format=input_format,
                        outputfile=output_path,
                        extra_args=[f"--pdf-engine={engine_path}"],
                    )
                    logger.info(f"PDF generated using {engine_name} ({engine_path})")
                    last_err = None
                    break
                except (RuntimeError, OSError) as err:
                    logger.debug(f"PDF engine {engine_name} failed: {err}")
                    last_err = err
                    continue

            if last_err:
                raise RuntimeError(
                    "PDF engine detected but conversion failed. "
                    f"Tried: {', '.join(name for name, _ in available_engines)}. "
                    f"Last error: {last_err}"
                ) from last_err
        else:
            pypandoc.convert_file(
                file_path,
                pandoc_output_format,
                format=input_format,
                outputfile=output_path,
            )

        job_store.update_job(job_id, progress=80)

        result["output_path"] = output_path

        # Get file size
        if os.path.exists(output_path):
            result["file_size_bytes"] = os.path.getsize(output_path)

        job_store.update_job(job_id, progress=90)

        # Persist result JSON
        result_json_path = os.path.join(settings.result_dir, f"{job_id}.json")
        with open(result_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        job_store.update_job(
            job_id,
            status="completed",
            progress=100,
            result_path=result_json_path,
            document_path=output_path,
        )

        logger.info(f"Document conversion completed: {job_id}")

    except Exception as e:
        logger.exception(f"Document conversion failed: {job_id}")
        result["errors"].append(str(e))
        job_store.update_job(
            job_id,
            status="failed",
            progress=100,
            error=str(e),
        )
