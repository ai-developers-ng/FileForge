"""OCR image preprocessing to improve Tesseract accuracy.

Profiles:
  none       — pass image through unchanged
  standard   — grayscale + auto-contrast + deskew
  aggressive — standard + upscale if low-res + denoise + sharpen
"""

import io
import logging

logger = logging.getLogger(__name__)

# Minimum width (px) below which "aggressive" upscales 2x.
# ~150 DPI on an A4 page ≈ 1240 px wide.
_LOW_RES_THRESHOLD = 1240


def preprocess_for_ocr(image, profile="standard"):
    """Apply OCR-optimised preprocessing to a PIL image.

    Args:
        image: PIL Image object (any mode)
        profile: "none", "standard", or "aggressive"

    Returns:
        Preprocessed PIL Image (mode "L" — grayscale)
    """
    if profile == "none":
        return image

    from PIL import ImageFilter, ImageOps

    # ── Step 1: Grayscale ─────────────────────────────────────────
    if image.mode != "L":
        image = image.convert("L")

    # ── Step 2: Upscale low-resolution images (aggressive only) ───
    if profile == "aggressive" and image.width < _LOW_RES_THRESHOLD:
        from PIL import Image as PilImage
        new_w = image.width * 2
        new_h = image.height * 2
        image = image.resize((new_w, new_h), resample=PilImage.LANCZOS)
        logger.info("Upscaled low-res image 2x to %dx%d", new_w, new_h)

    # ── Step 3: Deskew (standard + aggressive) ────────────────────
    try:
        image = _deskew(image)
        # Wand's PNG round-trip can return mode "1" (1-bit binary);
        # autocontrast and filters require mode "L".
        if image.mode != "L":
            image = image.convert("L")
    except Exception as exc:
        logger.warning("Deskew failed, skipping: %s", exc)

    # ── Step 4: Auto-contrast (standard + aggressive) ─────────────
    # Clips the top/bottom 1% of the histogram to improve contrast
    # on washed-out or very dark scans.
    image = ImageOps.autocontrast(image, cutoff=1)

    # ── Steps 5-6: Denoise + sharpen (aggressive only) ────────────
    if profile == "aggressive":
        # Median filter removes salt-and-pepper noise from scans
        image = image.filter(ImageFilter.MedianFilter(size=3))
        # Unsharp mask sharpens character edges for better segmentation
        image = image.filter(
            ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
        )

    return image


def _deskew(pil_image):
    """Correct document skew using Wand's deskew algorithm.

    Converts PIL → Wand, applies deskew, returns a new PIL image.
    Wand uses a background-colour flood-fill approach; it works best
    on white-background scanned documents.

    Args:
        pil_image: PIL Image (mode "L" recommended)

    Returns:
        Deskewed PIL Image
    """
    from wand.image import Image as WandImage
    from PIL import Image as PilImage

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)

    with WandImage(blob=buf.read()) as wand_img:
        # threshold is an absolute value; 40% of quantum_range is the
        # standard recommendation in the Wand / ImageMagick docs.
        threshold = 0.4 * wand_img.quantum_range
        wand_img.deskew(threshold)
        out_blob = wand_img.make_blob("PNG")

    result = PilImage.open(io.BytesIO(out_blob))
    return result.copy()
