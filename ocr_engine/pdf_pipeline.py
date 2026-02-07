import io
import logging
import os
import zipfile

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


def merge_pdfs(paths, output_path):
    writer = PdfWriter()
    for path in paths:
        reader = PdfReader(path)
        for page in reader.pages:
            writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def split_pdf(path, output_dir, job_id):
    reader = PdfReader(path)
    output_paths = []
    for i, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        out_path = os.path.join(output_dir, f"{job_id}_page_{i}.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)
        output_paths.append(out_path)
    return output_paths


def compress_pdf(path, output_path):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # Compress after all pages are added
    for page in writer.pages:
        page.compress_content_streams()
    writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def rotate_pdf(path, output_path, degrees=90):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(int(degrees))
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def extract_pages(path, output_path, page_range):
    """Extract specific pages. page_range is a string like '1,3,5-8'."""
    reader = PdfReader(path)
    total = len(reader.pages)
    indices = _parse_page_range(page_range, total)
    if not indices:
        raise ValueError(f"No valid pages in range '{page_range}' (document has {total} pages)")
    writer = PdfWriter()
    for idx in indices:
        writer.add_page(reader.pages[idx])
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def delete_pages(path, output_path, page_range):
    """Delete specific pages. page_range is a string like '1,3,5-8'."""
    reader = PdfReader(path)
    total = len(reader.pages)
    to_delete = set(_parse_page_range(page_range, total))
    if not to_delete:
        raise ValueError(f"No valid pages in range '{page_range}' (document has {total} pages)")
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i not in to_delete:
            writer.add_page(page)
    if len(writer.pages) == 0:
        raise ValueError("Cannot delete all pages from a PDF")
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def add_watermark(path, output_path, text="WATERMARK", opacity=0.3, font_size=60, rotation=45):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        watermark_pdf = _create_watermark_page(text, page_width, page_height, opacity, font_size, rotation)
        watermark_reader = PdfReader(watermark_pdf)
        page.merge_page(watermark_reader.pages[0])
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def protect_pdf(path, output_path, password):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def unlock_pdf(path, output_path, password):
    reader = PdfReader(path)
    if reader.is_encrypted:
        if not reader.decrypt(password):
            raise ValueError("Incorrect password")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def pdf_to_images(path, output_dir, job_id, fmt="png", dpi=200):
    from pdf2image import convert_from_path

    images = convert_from_path(path, dpi=dpi, fmt=fmt)
    output_paths = []
    for i, img in enumerate(images, start=1):
        out_path = os.path.join(output_dir, f"{job_id}_page_{i}.{fmt}")
        img.save(out_path, fmt.upper())
        output_paths.append(out_path)
    return output_paths


def images_to_pdf(image_paths, output_path):
    if not image_paths:
        raise ValueError("No images provided")
    imgs = []
    for p in image_paths:
        img = Image.open(p)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        imgs.append(img)
    first = imgs[0]
    rest = imgs[1:] if len(imgs) > 1 else []
    first.save(output_path, "PDF", save_all=True, append_images=rest, resolution=150)
    return output_path


def add_page_numbers(path, output_path, position="bottom-center", start_num=1, font_size=12):
    reader = PdfReader(path)
    writer = PdfWriter()
    total = len(reader.pages)
    for i, page in enumerate(reader.pages):
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        num = start_num + i
        overlay_pdf = _create_page_number_overlay(num, total, page_width, page_height, position, font_size)
        overlay_reader = PdfReader(overlay_pdf)
        page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


def edit_metadata(path, output_path, title=None, author=None, subject=None, keywords=None):
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    metadata = {}
    if title is not None:
        metadata["/Title"] = title
    if author is not None:
        metadata["/Author"] = author
    if subject is not None:
        metadata["/Subject"] = subject
    if keywords is not None:
        metadata["/Keywords"] = keywords
    if metadata:
        writer.add_metadata(metadata)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


# ── Helpers ──────────────────────────────────────────────────────

def _parse_page_range(page_range, total):
    """Parse a page range string like '1,3,5-8' into 0-based indices."""
    indices = []
    for part in page_range.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = max(1, int(start.strip()))
            end = min(total, int(end.strip()))
            indices.extend(range(start - 1, end))
        else:
            page_num = int(part)
            if 1 <= page_num <= total:
                indices.append(page_num - 1)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            result.append(idx)
    return result


def _create_watermark_page(text, width, height, opacity, font_size, rotation):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.saveState()
    c.setFont("Helvetica-Bold", font_size)
    c.setFillAlpha(opacity)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.translate(width / 2, height / 2)
    c.rotate(rotation)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _create_page_number_overlay(page_num, total_pages, width, height, position, font_size):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    text = f"{page_num} / {total_pages}"
    c.setFont("Helvetica", font_size)
    margin = 36  # 0.5 inch
    if position == "bottom-center":
        c.drawCentredString(width / 2, margin, text)
    elif position == "bottom-left":
        c.drawString(margin, margin, text)
    elif position == "bottom-right":
        c.drawRightString(width - margin, margin, text)
    elif position == "top-center":
        c.drawCentredString(width / 2, height - margin, text)
    elif position == "top-left":
        c.drawString(margin, height - margin, text)
    elif position == "top-right":
        c.drawRightString(width - margin, height - margin, text)
    else:
        c.drawCentredString(width / 2, margin, text)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ── Job Dispatcher ───────────────────────────────────────────────

def process_pdf_job(job_id, file_paths, options, settings, job_store):
    try:
        job_store.update_job(job_id, status="running", progress=0)
        pdf_mode = options.get("pdf_mode", "merge")

        if pdf_mode == "merge":
            output_path = os.path.join(settings.result_dir, f"{job_id}_merged.pdf")
            merge_pdfs(file_paths, output_path)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "split":
            page_paths = split_pdf(file_paths[0], settings.result_dir, job_id)
            zip_path = os.path.join(settings.result_dir, f"{job_id}_split.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in page_paths:
                    zf.write(p, os.path.basename(p))
            for p in page_paths:
                os.remove(p)
            job_store.update_job(job_id, status="completed", pdf_path=zip_path, progress=100)

        elif pdf_mode == "compress":
            output_path = os.path.join(settings.result_dir, f"{job_id}_compressed.pdf")
            compress_pdf(file_paths[0], output_path)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "rotate":
            degrees = int(options.get("rotate_degrees", 90))
            output_path = os.path.join(settings.result_dir, f"{job_id}_rotated.pdf")
            rotate_pdf(file_paths[0], output_path, degrees)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "extract":
            page_range = options.get("page_range", "1")
            output_path = os.path.join(settings.result_dir, f"{job_id}_extracted.pdf")
            extract_pages(file_paths[0], output_path, page_range)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "delete":
            page_range = options.get("page_range", "1")
            output_path = os.path.join(settings.result_dir, f"{job_id}_trimmed.pdf")
            delete_pages(file_paths[0], output_path, page_range)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "watermark":
            text = options.get("watermark_text", "WATERMARK")
            opacity = float(options.get("watermark_opacity", 0.3))
            font_size = int(options.get("watermark_font_size", 60))
            rotation = int(options.get("watermark_rotation", 45))
            output_path = os.path.join(settings.result_dir, f"{job_id}_watermarked.pdf")
            add_watermark(file_paths[0], output_path, text, opacity, font_size, rotation)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "protect":
            password = options.get("password", "")
            if not password:
                job_store.update_job(job_id, status="failed", error="Password is required", progress=100)
                return
            output_path = os.path.join(settings.result_dir, f"{job_id}_protected.pdf")
            protect_pdf(file_paths[0], output_path, password)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "unlock":
            password = options.get("password", "")
            if not password:
                job_store.update_job(job_id, status="failed", error="Password is required", progress=100)
                return
            output_path = os.path.join(settings.result_dir, f"{job_id}_unlocked.pdf")
            unlock_pdf(file_paths[0], output_path, password)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "to_images":
            fmt = options.get("image_format", "png")
            dpi = int(options.get("dpi", 200))
            img_paths = pdf_to_images(file_paths[0], settings.result_dir, job_id, fmt, dpi)
            zip_path = os.path.join(settings.result_dir, f"{job_id}_images.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in img_paths:
                    zf.write(p, os.path.basename(p))
            for p in img_paths:
                os.remove(p)
            job_store.update_job(job_id, status="completed", pdf_path=zip_path, progress=100)

        elif pdf_mode == "from_images":
            output_path = os.path.join(settings.result_dir, f"{job_id}_combined.pdf")
            images_to_pdf(file_paths, output_path)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "page_numbers":
            position = options.get("number_position", "bottom-center")
            start_num = int(options.get("start_number", 1))
            output_path = os.path.join(settings.result_dir, f"{job_id}_numbered.pdf")
            add_page_numbers(file_paths[0], output_path, position, start_num)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        elif pdf_mode == "metadata":
            title = options.get("meta_title") or None
            author = options.get("meta_author") or None
            subject = options.get("meta_subject") or None
            keywords = options.get("meta_keywords") or None
            output_path = os.path.join(settings.result_dir, f"{job_id}_metadata.pdf")
            edit_metadata(file_paths[0], output_path, title, author, subject, keywords)
            job_store.update_job(job_id, status="completed", pdf_path=output_path, progress=100)

        else:
            job_store.update_job(job_id, status="failed", error=f"Unknown pdf_mode: {pdf_mode}", progress=100)
    except Exception as exc:
        logger.error("PDF job %s failed: %s", job_id, exc, exc_info=True)
        job_store.update_job(job_id, status="failed", error=str(exc), progress=100)
