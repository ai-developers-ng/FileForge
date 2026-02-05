"""Video conversion pipeline using FFmpeg."""

import json
import logging
import os
import subprocess
from dataclasses import dataclass

from .storage import video_result_path

logger = logging.getLogger(__name__)


@dataclass
class VideoConversionOptions:
    """Options for video conversion."""
    output_format: str = "mp4"
    quality: str = "medium"  # low, medium, high


# Output format mapping (user-friendly name to FFmpeg settings)
OUTPUT_FORMAT_MAP = {
    "mp4": {"ext": "mp4", "vcodec": "libx264", "acodec": "aac"},
    "webm": {"ext": "webm", "vcodec": "libvpx-vp9", "acodec": "libopus"},
    "avi": {"ext": "avi", "vcodec": "mpeg4", "acodec": "mp3"},
    "mkv": {"ext": "mkv", "vcodec": "libx264", "acodec": "aac"},
    "mov": {"ext": "mov", "vcodec": "libx264", "acodec": "aac"},
    "gif": {"ext": "gif", "vcodec": "gif", "acodec": None},
    "wmv": {"ext": "wmv", "vcodec": "wmv2", "acodec": "wmav2"},
    "flv": {"ext": "flv", "vcodec": "flv1", "acodec": "mp3"},
}

# Quality presets (CRF values for x264, lower = better quality)
QUALITY_PRESETS = {
    "low": {"crf": "28", "preset": "faster"},
    "medium": {"crf": "23", "preset": "medium"},
    "high": {"crf": "18", "preset": "slow"},
}


def get_video_info(file_path):
    """Get video duration and metadata using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data.get("format", {}).get("duration", 0))
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            return {
                "duration": duration,
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "codec": video_stream.get("codec_name"),
            }
    except Exception as e:
        logger.warning(f"Could not get video info: {e}")
    return {"duration": 0}


def process_video_job(job_id, file_path, options, settings, job_store):
    """Process a video conversion job using FFmpeg.

    Args:
        job_id: Unique job identifier
        file_path: Path to the uploaded video file
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
        conv_options = VideoConversionOptions(
            output_format=options.get("output_format", "mp4"),
            quality=options.get("quality", "medium"),
        )

        job_store.update_job(job_id, progress=5)

        # Get video info
        video_info = get_video_info(file_path)
        result["input_duration"] = video_info.get("duration", 0)
        result["input_width"] = video_info.get("width")
        result["input_height"] = video_info.get("height")

        job_store.update_job(job_id, progress=10)

        # Determine output format settings
        format_settings = OUTPUT_FORMAT_MAP.get(conv_options.output_format)
        if not format_settings:
            raise ValueError(f"Unsupported output format: {conv_options.output_format}")

        quality_settings = QUALITY_PRESETS.get(conv_options.quality, QUALITY_PRESETS["medium"])

        output_ext = format_settings["ext"]
        output_path = video_result_path(settings.result_dir, job_id, output_ext)

        job_store.update_job(job_id, progress=15)

        # Build FFmpeg command
        cmd = ["ffmpeg", "-y", "-i", file_path]

        # Add video codec settings
        if format_settings["vcodec"] == "gif":
            # Special handling for GIF - create palette for better quality
            cmd.extend([
                "-vf", "fps=10,scale=480:-1:flags=lanczos",
                "-loop", "0"
            ])
        else:
            cmd.extend(["-c:v", format_settings["vcodec"]])

            # Add quality settings for supported codecs
            if format_settings["vcodec"] in ("libx264", "libx265"):
                cmd.extend([
                    "-crf", quality_settings["crf"],
                    "-preset", quality_settings["preset"]
                ])
            elif format_settings["vcodec"] == "libvpx-vp9":
                # VP9 uses different quality settings
                crf = quality_settings["crf"]
                cmd.extend(["-crf", crf, "-b:v", "0"])

        # Add audio codec if applicable
        if format_settings["acodec"]:
            cmd.extend(["-c:a", format_settings["acodec"]])
            if format_settings["acodec"] in ("aac", "libopus"):
                cmd.extend(["-b:a", "192k"])
        elif format_settings["vcodec"] == "gif":
            cmd.extend(["-an"])  # No audio for GIF

        cmd.append(output_path)

        logger.info(f"Converting video: {' '.join(cmd)}")

        job_store.update_job(job_id, progress=20)

        # Run FFmpeg
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for completion (could add progress parsing here)
        stdout, stderr = process.communicate(timeout=600)  # 10 minute timeout

        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {stderr}")

        job_store.update_job(job_id, progress=85)

        result["output_path"] = output_path
        result["output_format"] = conv_options.output_format

        # Get output file size
        if os.path.exists(output_path):
            result["file_size_bytes"] = os.path.getsize(output_path)

            # Get output video info
            output_info = get_video_info(output_path)
            result["output_duration"] = output_info.get("duration", 0)
            result["output_width"] = output_info.get("width")
            result["output_height"] = output_info.get("height")

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
            video_path=output_path,
        )

        logger.info(f"Video conversion completed: {job_id}")

    except subprocess.TimeoutExpired:
        logger.exception(f"Video conversion timed out: {job_id}")
        result["errors"].append("Conversion timed out (max 10 minutes)")
        job_store.update_job(
            job_id,
            status="failed",
            progress=100,
            error="Conversion timed out",
        )
    except Exception as e:
        logger.exception(f"Video conversion failed: {job_id}")
        result["errors"].append(str(e))
        job_store.update_job(
            job_id,
            status="failed",
            progress=100,
            error=str(e),
        )
