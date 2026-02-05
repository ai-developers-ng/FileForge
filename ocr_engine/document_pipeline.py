"""Document conversion pipeline using Pandoc via pypandoc."""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import pypandoc

from .storage import document_result_path

logger = logging.getLogger(__name__)


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
    ".txt": "plain",
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

        # Perform conversion - try with pdflatex for PDF, fall back if not available
        try:
            if pandoc_output_format == "pdf":
                # Try with pdflatex first for better PDF output
                try:
                    pypandoc.convert_file(
                        file_path,
                        pandoc_output_format,
                        format=input_format,
                        outputfile=output_path,
                        extra_args=["--pdf-engine=pdflatex"],
                    )
                except (RuntimeError, OSError) as pdf_err:
                    # pdflatex not available, try default engine
                    logger.warning(f"pdflatex not available ({pdf_err}), trying default PDF engine")
                    pypandoc.convert_file(
                        file_path,
                        pandoc_output_format,
                        format=input_format,
                        outputfile=output_path,
                    )
            else:
                pypandoc.convert_file(
                    file_path,
                    pandoc_output_format,
                    format=input_format,
                    outputfile=output_path,
                )
        except RuntimeError as e:
            raise

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
