import io

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def write_text_pdf(output_path, title, text):
    page_width, page_height = letter
    pdf = canvas.Canvas(output_path, pagesize=letter)
    pdf.setTitle(title)
    text_obj = pdf.beginText(40, page_height - 60)
    text_obj.setFont("Helvetica", 11)

    for line in (text or "").splitlines():
        if text_obj.getY() < 60:
            pdf.drawText(text_obj)
            pdf.showPage()
            text_obj = pdf.beginText(40, page_height - 60)
            text_obj.setFont("Helvetica", 11)
        text_obj.textLine(line)

    pdf.drawText(text_obj)
    pdf.showPage()
    pdf.save()


def write_ocr_pdf_from_images(output_path, title, images, page_texts, page_pdf_bytes=None):
    """Create a PDF with images and overlaid OCR text.
    
    Args:
        output_path: Path where PDF will be saved
        title: PDF document title
        images: List of PIL Image objects
        page_texts: List of text strings (one per page/image)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not images:
        # Fallback to text-only PDF if no images
        write_text_pdf(output_path, title, "\n\n".join(page_texts) if page_texts else "")
        return
    
    logger.info(f"Creating PDF with {len(images)} images and {len(page_texts)} page texts")
    for idx, text in enumerate(page_texts):
        logger.info(f"Page {idx + 1} text length: {len(text)} chars, preview: {text[:100] if text else '(empty)'}")
    
    writer = PdfWriter()

    for index, image in enumerate(images):
        if page_pdf_bytes and index < len(page_pdf_bytes) and page_pdf_bytes[index]:
            try:
                tesseract_reader = PdfReader(io.BytesIO(page_pdf_bytes[index]))
                if tesseract_reader.pages:
                    writer.add_page(tesseract_reader.pages[0])
                    continue
            except Exception:
                logger.warning(f"Page {index + 1}: Failed to use Tesseract PDF bytes, falling back to overlay")

        # Ensure image is in compatible mode
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        
        width, height = image.size
        
        # Create a buffer for the image-only PDF
        image_buffer = io.BytesIO()
        image_pdf = canvas.Canvas(image_buffer, pagesize=(width, height))
        image_pdf.setTitle(title)
        
        # Draw the image
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)
        image_pdf.drawImage(ImageReader(image_bytes), 0, 0, width=width, height=height)
        image_pdf.showPage()
        image_pdf.save()
        
        # Create a buffer for the text-only PDF
        text_buffer = io.BytesIO()
        text_pdf = canvas.Canvas(text_buffer, pagesize=(width, height))
        
        # Get text for this page
        page_text = page_texts[index] if index < len(page_texts) else ""
        
        logger.info(f"Page {index + 1}: Adding {len(page_text)} characters of text")
        
        if page_text:
            # Create invisible text layer using rendering mode 3
            # This is the standard way to create searchable but invisible text
            y_position = height - 40
            font_size = 10
            
            text_obj = text_pdf.beginText(10, y_position)
            text_obj.setFont("Helvetica", font_size)
            text_obj.setTextRenderMode(3)  # Mode 3: invisible (neither fill nor stroke)
            
            lines_added = 0
            for line in page_text.splitlines():
                if line.strip():
                    text_obj.textLine(line)
                    lines_added += 1
            
            text_pdf.drawText(text_obj)
            logger.info(f"Page {index + 1}: Added {lines_added} lines of invisible text")
        else:
            logger.warning(f"Page {index + 1}: No text to add!")
        
        text_pdf.showPage()
        text_pdf.save()
        
        # Merge the image PDF and text PDF
        image_buffer.seek(0)
        text_buffer.seek(0)
        
        image_reader = PdfReader(image_buffer)
        text_reader = PdfReader(text_buffer)
        
        # Get the pages
        image_page = image_reader.pages[0]
        text_page = text_reader.pages[0]
        
        # Merge text layer onto image layer
        image_page.merge_page(text_page)
        
        writer.add_page(image_page)

    with open(output_path, "wb") as handle:
        writer.write(handle)
    
    logger.info(f"PDF written to {output_path}")
