from dataclasses import dataclass

from .ocr_preprocess import preprocess_for_ocr


@dataclass
class OcrResult:
    text: str
    engine: str
    detail: dict


def _load_pil():
    from PIL import Image

    return Image


def _load_tesseract():
    import pytesseract

    return pytesseract


def run_tesseract(image, lang="eng", psm=6, oem=1, preprocess="standard"):
    """Run Tesseract OCR on an image.

    Args:
        image: PIL Image object
        lang: Tesseract language code (default: eng)
        psm: Page segmentation mode (default: 6 — single uniform text block)
        oem: OCR engine mode (default: 1 — LSTM neural net only)
        preprocess: Preprocessing profile ("none", "standard", "aggressive")

    Returns:
        OcrResult with extracted text
    """
    pytesseract = _load_tesseract()

    image = preprocess_for_ocr(image, profile=preprocess)

    custom_config = f"--oem {oem} --psm {psm}"

    # Get text and data for confidence scores
    text = pytesseract.image_to_string(image, lang=lang, config=custom_config)
    pdf_bytes = None
    try:
        # Generate searchable PDF with coordinates for better text selection.
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(image, extension="pdf", lang=lang, config=custom_config)
    except Exception:
        pdf_bytes = None

    # Get detailed OCR data for confidence metrics
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang=lang, config=custom_config)
        confidences = [conf for conf in data['conf'] if conf != -1]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    except Exception:
        avg_confidence = 0.0
    
    detail = {"confidence": avg_confidence}
    if pdf_bytes:
        detail["tesseract_pdf"] = pdf_bytes

    return OcrResult(
        text=text.strip(),
        engine="tesseract",
        detail=detail
    )


def open_image(path):
    Image = _load_pil()
    return Image.open(path)
