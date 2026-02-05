"""Audio conversion pipeline using pydub/FFmpeg."""

import json
import logging
import os
from dataclasses import dataclass

from pydub import AudioSegment

from .storage import audio_result_path

logger = logging.getLogger(__name__)


@dataclass
class AudioConversionOptions:
    """Options for audio conversion."""
    output_format: str = "mp3"
    bitrate: str = "192"


# Output format mapping (user-friendly name to pydub format)
OUTPUT_FORMAT_MAP = {
    "mp3": "mp3",
    "wav": "wav",
    "flac": "flac",
    "aac": "adts",
    "ogg": "ogg",
    "m4a": "ipod",
    "opus": "opus",
}

# File extensions for output formats
OUTPUT_EXTENSIONS = {
    "mp3": "mp3",
    "wav": "wav",
    "flac": "flac",
    "aac": "aac",
    "ogg": "ogg",
    "m4a": "m4a",
    "opus": "opus",
}

# Lossless formats (don't use bitrate parameter)
LOSSLESS_FORMATS = {"wav", "flac"}


def process_audio_job(job_id, file_path, options, settings, job_store):
    """Process an audio conversion job using pydub/FFmpeg.

    Args:
        job_id: Unique job identifier
        file_path: Path to the uploaded audio/video file
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
        conv_options = AudioConversionOptions(
            output_format=options.get("output_format", "mp3"),
            bitrate=options.get("bitrate", "192"),
        )

        job_store.update_job(job_id, progress=10)

        # Load audio/video file (pydub/FFmpeg handles extraction from video)
        logger.info(f"Loading audio from {file_path}")
        audio = AudioSegment.from_file(file_path)

        result["duration_ms"] = len(audio)
        result["channels"] = audio.channels
        result["sample_rate"] = audio.frame_rate

        job_store.update_job(job_id, progress=40)

        # Determine output format
        pydub_format = OUTPUT_FORMAT_MAP.get(conv_options.output_format)
        if not pydub_format:
            raise ValueError(f"Unsupported output format: {conv_options.output_format}")

        output_ext = OUTPUT_EXTENSIONS.get(conv_options.output_format, conv_options.output_format)
        output_path = audio_result_path(settings.result_dir, job_id, output_ext)

        job_store.update_job(job_id, progress=50)

        # Export with appropriate settings
        logger.info(f"Converting to {conv_options.output_format} at {conv_options.bitrate}kbps")

        export_params = {
            "format": pydub_format,
        }

        # Only add bitrate for lossy formats
        if conv_options.output_format not in LOSSLESS_FORMATS:
            export_params["bitrate"] = f"{conv_options.bitrate}k"

        # Special handling for certain formats
        if conv_options.output_format == "mp3":
            export_params["parameters"] = ["-q:a", "0"]  # High quality VBR
        elif conv_options.output_format == "aac":
            export_params["parameters"] = ["-c:a", "aac"]
        elif conv_options.output_format == "opus":
            export_params["parameters"] = ["-c:a", "libopus"]
            export_params["format"] = "opus"

        audio.export(output_path, **export_params)

        job_store.update_job(job_id, progress=80)

        result["output_path"] = output_path
        result["output_format"] = conv_options.output_format

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
            audio_path=output_path,
        )

        logger.info(f"Audio conversion completed: {job_id}")

    except Exception as e:
        logger.exception(f"Audio conversion failed: {job_id}")
        result["errors"].append(str(e))
        job_store.update_job(
            job_id,
            status="failed",
            progress=100,
            error=str(e),
        )
