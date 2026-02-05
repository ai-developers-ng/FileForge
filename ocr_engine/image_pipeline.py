"""Image conversion pipeline using ImageMagick via Wand."""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from wand.image import Image
from wand.color import Color

from .storage import image_result_path

logger = logging.getLogger(__name__)


@dataclass
class ImageConversionOptions:
    """Options for image conversion."""
    output_format: str = "png"
    quality: int = 85
    resize_width: Optional[int] = None
    resize_height: Optional[int] = None
    resize_percent: Optional[int] = None
    dpi: Optional[int] = None
    grayscale: bool = False
    rotation: int = 0
    brightness: float = 1.0
    contrast: float = 1.0


# Common output formats for the UI
OUTPUT_FORMATS = {
    "png": "png",
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "webp": "webp",
    "gif": "gif",
    "bmp": "bmp",
    "tiff": "tiff",
    "tif": "tiff",
    "ico": "ico",
    "pdf": "pdf",
    "svg": "svg",
    "heic": "heic",
    "avif": "avif",
    "jxl": "jxl",
}


def process_image_job(job_id, file_path, options, settings, job_store):
    """Process an image conversion job using ImageMagick.

    Args:
        job_id: Unique job identifier
        file_path: Path to the uploaded image file
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
        conv_options = ImageConversionOptions(
            output_format=options.get("output_format", "png"),
            quality=int(options.get("quality", 85)),
            resize_width=_parse_int(options.get("resize_width")),
            resize_height=_parse_int(options.get("resize_height")),
            resize_percent=_parse_int(options.get("resize_percent")),
            dpi=_parse_int(options.get("dpi")),
            grayscale=options.get("grayscale", False),
            rotation=int(options.get("rotation", 0)),
            brightness=float(options.get("brightness", 1.0)),
            contrast=float(options.get("contrast", 1.0)),
        )

        job_store.update_job(job_id, progress=10)

        # Open image with ImageMagick
        with Image(filename=file_path) as img:
            original_width = img.width
            original_height = img.height
            original_format = img.format

            result["original_size"] = {"width": original_width, "height": original_height}
            result["original_format"] = original_format

            job_store.update_job(job_id, progress=20)

            # 1. Resize
            if conv_options.resize_width or conv_options.resize_height or conv_options.resize_percent:
                _apply_resize(img, conv_options)

            job_store.update_job(job_id, progress=40)

            # 2. Rotation
            if conv_options.rotation != 0:
                img.rotate(conv_options.rotation)

            job_store.update_job(job_id, progress=50)

            # 3. Grayscale
            if conv_options.grayscale:
                img.type = 'grayscale'

            # 4. Brightness adjustment (modulate)
            if conv_options.brightness != 1.0:
                brightness_percent = conv_options.brightness * 100
                img.modulate(brightness=brightness_percent)

            # 5. Contrast adjustment
            if conv_options.contrast != 1.0:
                # Wand uses sigmoidal contrast
                # contrast > 1 increases, < 1 decreases
                if conv_options.contrast > 1.0:
                    sharpen = True
                    strength = (conv_options.contrast - 1.0) * 5 + 3
                else:
                    sharpen = False
                    strength = (1.0 - conv_options.contrast) * 5 + 3
                img.sigmoidal_contrast(sharpen=sharpen, strength=strength, midpoint=0.5 * img.quantum_range)

            job_store.update_job(job_id, progress=70)

            # 6. Set DPI/resolution
            if conv_options.dpi:
                img.resolution = (conv_options.dpi, conv_options.dpi)

            # 7. Set quality for lossy formats
            img.compression_quality = conv_options.quality

            # 8. Determine output format
            output_ext = conv_options.output_format.lower()
            if output_ext in OUTPUT_FORMATS:
                img.format = OUTPUT_FORMATS[output_ext]
            else:
                img.format = output_ext

            # Handle alpha channel for formats that don't support it
            if output_ext in ("jpg", "jpeg", "bmp") and img.alpha_channel:
                img.background_color = Color('white')
                img.alpha_channel = 'remove'

            # Generate output path
            output_path = image_result_path(
                settings.result_dir,
                job_id,
                output_ext if output_ext not in ("jpeg",) else "jpg",
            )

            # Save
            img.save(filename=output_path)

            result["output_path"] = output_path
            result["output_size"] = {"width": img.width, "height": img.height}
            result["output_format"] = conv_options.output_format

        # Get file size after saving
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
            image_path=output_path,
        )

        logger.info(f"Image conversion completed: {job_id}")

    except Exception as e:
        logger.exception(f"Image conversion failed: {job_id}")
        result["errors"].append(str(e))
        job_store.update_job(
            job_id,
            status="failed",
            progress=100,
            error=str(e),
        )


def _parse_int(value) -> Optional[int]:
    """Parse an integer value, returning None if empty or invalid."""
    if value is None or value == "" or value == "null":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _apply_resize(img: Image, options: ImageConversionOptions):
    """Resize image with aspect ratio preservation.

    Args:
        img: Wand Image object (modified in place)
        options: Conversion options with resize settings
    """
    original_width = img.width
    original_height = img.height

    if options.resize_percent:
        new_width = int(original_width * options.resize_percent / 100)
        new_height = int(original_height * options.resize_percent / 100)
    elif options.resize_width and options.resize_height:
        new_width = options.resize_width
        new_height = options.resize_height
    elif options.resize_width:
        ratio = options.resize_width / original_width
        new_width = options.resize_width
        new_height = int(original_height * ratio)
    elif options.resize_height:
        ratio = options.resize_height / original_height
        new_height = options.resize_height
        new_width = int(original_width * ratio)
    else:
        return

    # Ensure minimum size of 1x1
    new_width = max(1, new_width)
    new_height = max(1, new_height)

    img.resize(new_width, new_height)
