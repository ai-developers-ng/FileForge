import mimetypes
import os
import traceback
import logging
from concurrent.futures import ThreadPoolExecutor as _PageExecutor, as_completed as _as_completed

from .cache import OcrCache, hash_file, hash_image, hash_options, _PAGE_OPTS_KEYS, _FILE_OPTS_KEYS
from .ocr import open_image, run_tesseract
from .pdf_output import write_ocr_pdf_from_images, write_text_pdf
from .storage import result_paths
from .tika_client import TikaClient

# Configure logger
logger = logging.getLogger(__name__)


def _ocr_page_task(args):
    """Parallel-safe per-page OCR worker with page-level cache support.

    Args:
        args: tuple of (idx, image, engine, lang, psm, oem, preprocess, deskew,
                        cache, page_opts_hash)
              cache and page_opts_hash may both be None when caching is disabled.

    Returns:
        tuple of (idx, ocr_result_dict, error_msg_or_None)
    """
    idx, image, engine, lang, psm, oem, preprocess, deskew, cache, page_opts_hash = args

    # ── Page cache check ──────────────────────────────────────────────────────
    image_hash = None
    if cache is not None:
        image_hash = hash_image(image)
        cached = cache.get_page(image_hash, page_opts_hash)
        if cached is not None:
            logger.info("Page %d: cache HIT (skipping Tesseract)", idx)
            return idx, cached, None

    # ── Cache miss — run Tesseract ────────────────────────────────────────────
    local_errors = []
    local_result = {"errors": local_errors}
    ocr_text = _run_ocr_engine(
        image, engine, local_result,
        lang=lang, psm=psm, oem=oem, preprocess=preprocess, deskew=deskew,
    )
    error_msg = local_errors[0] if local_errors else None

    # ── Store result in page cache ────────────────────────────────────────────
    if cache is not None and not error_msg:
        if image_hash is None:
            image_hash = hash_image(image)
        cache.set_page(image_hash, page_opts_hash, ocr_text)

    return idx, ocr_text, error_msg


def _is_pdf(file_path):
    return os.path.splitext(file_path)[1].lower() == ".pdf"


def _has_embedded_text(file_path, min_chars=100):
    """Return True if the PDF has extractable text (i.e. digital, not scanned).

    Checks the first three pages for at least min_chars of real text.  If found,
    the document is a native digital PDF and deskew can be safely skipped.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        for page in reader.pages[:3]:
            if len((page.extract_text() or "").strip()) >= min_chars:
                return True
    except Exception:
        pass
    return False


def _is_image(file_path):
    mime = mimetypes.guess_type(file_path)[0] or ""
    return mime.startswith("image/")


def _pdf_to_images(file_path, batch_size=10, dpi=300):
    """Convert PDF to images in batches to reduce memory usage.

    For large PDFs, processing all pages at once can cause OOM errors.
    This function processes pages in batches and yields them one at a time.

    Args:
        file_path: Path to the PDF file
        batch_size: Number of pages to process in each batch (default: 10)
        dpi: Resolution for rendering (default: 300 — optimal for Tesseract accuracy)

    Returns:
        List of PIL Image objects
    """
    from pdf2image import convert_from_path, pdfinfo_from_path
    import gc

    # Get total page count
    try:
        info = pdfinfo_from_path(file_path)
        total_pages = info.get('Pages', 0)
        logger.info(f"PDF has {total_pages} pages, will process in batches of {batch_size} at {dpi} DPI")
    except Exception as e:
        logger.warning(f"Could not get page count, processing all at once: {e}")
        return convert_from_path(file_path, dpi=dpi)

    # If small PDF, process all at once
    if total_pages <= batch_size:
        return convert_from_path(file_path, dpi=dpi)

    # Process in batches for large PDFs
    all_images = []
    for start_page in range(1, total_pages + 1, batch_size):
        end_page = min(start_page + batch_size - 1, total_pages)
        logger.info(f"Converting pages {start_page}-{end_page}/{total_pages}")

        try:
            batch_images = convert_from_path(
                file_path,
                first_page=start_page,
                last_page=end_page,
                dpi=dpi,
            )
            all_images.extend(batch_images)

            # Force garbage collection after each batch
            gc.collect()
        except Exception as e:
            logger.error(f"Failed to convert pages {start_page}-{end_page}: {e}")
            raise

    return all_images


def process_job(job_id, file_path, options, settings, job_store, cancel_event=None, cache=None):
    """Process a document extraction job.

    Modes:
    - 'text': Text extraction only (Tika), no OCR, no PDF output
    - 'ocr': OCR only, generates PDF with images + OCR layer, no text extraction
    - 'both': OCR + Text extraction, generates PDF and extracts text from it

    Args:
        job_id: Unique job identifier
        file_path: Path to the uploaded file
        options: Processing options (mode, ocr_engine, etc.)
        settings: Application settings
        job_store: Job storage instance
        cancel_event: Optional threading.Event for cooperative cancellation
        cache: Optional OcrCache instance (None = caching disabled)
    """
    mode = options.get("mode", "text")
    ocr_engine = options.get("ocr_engine", "tesseract")
    lang = options.get("lang", "eng")
    psm = int(options.get("psm", 6))
    oem = int(options.get("oem", 1))
    preprocess = options.get("preprocess", "standard")
    
    logger.info(f"Processing job {job_id}: file={os.path.basename(file_path)}, "
               f"mode={mode}, ocr_engine={ocr_engine}")

    result = {
        "job_id": job_id,
        "filename": os.path.basename(file_path),
        "tika_text": "",
        "ocr_text": "",
        "final_text": "",
        "metadata": {},
        "pages": [],
        "errors": [],
        "options": options,
    }

    try:
        job_store.update_job(job_id, status="running", progress=0)

        # Mode: 'text' - Text extraction only, no OCR
        if mode == "text":
            logger.info(f"Text-only mode for job {job_id}")

            # ── File cache check (text mode) ──────────────────────────────────
            file_hash = None
            file_opts_hash = None
            file_cache_hit = False
            if cache is not None:
                file_hash = hash_file(file_path)
                file_opts_hash = hash_options(options, keys=_FILE_OPTS_KEYS)
                cached = cache.get_file(file_hash, file_opts_hash)
                if cached is not None:
                    result["tika_text"] = cached.get("tika_text", "")
                    result["metadata"] = cached.get("metadata", {})
                    result["final_text"] = cached.get("final_text", "")
                    logger.info(f"File cache HIT for job {job_id} (skipping Tika)")
                    file_cache_hit = True

            if not file_cache_hit:
                try:
                    tika = TikaClient(settings.tika_url)
                    result["tika_text"] = tika.extract_text(file_path)
                    result["metadata"] = tika.extract_metadata(file_path)
                    result["final_text"] = result["tika_text"]
                    logger.info(f"Tika extraction completed. Text length: {len(result['tika_text'])}")
                except Exception as exc:
                    error_msg = f"Tika extraction failed: {exc}"
                    logger.error(error_msg, exc_info=True)
                    result["errors"].append(error_msg)

                # ── Cache successful extraction ────────────────────────────────
                if cache is not None and not result["errors"]:
                    if file_hash is None:
                        file_hash = hash_file(file_path)
                        file_opts_hash = hash_options(options, keys=_FILE_OPTS_KEYS)
                    cache.set_file(file_hash, file_opts_hash, {
                        "tika_text": result["tika_text"],
                        "metadata": result["metadata"],
                        "final_text": result["final_text"],
                    })

            job_store.update_job(job_id, progress=100)

            # Save results (no PDF generation for text-only mode)
            json_path, text_path, pdf_path = _persist_result(
                result, settings.result_dir, job_id, ocr_images=[], generate_pdf=False
            )
            
        # Mode: 'ocr' or 'both' - OCR processing required
        elif mode in ("ocr", "both"):
            logger.info(f"OCR mode ({mode}) for job {job_id}")
            
            # Convert document to images
            ocr_images = []
            # Auto-detect whether this is a scanned vs. digital PDF so we can
            # skip the expensive deskew step for native digital documents.
            is_scanned = True
            if _is_pdf(file_path):
                is_scanned = not _has_embedded_text(file_path)
                logger.info(f"PDF scan detection for job {job_id}: {'scanned' if is_scanned else 'digital (deskew disabled)'}")
            if _is_pdf(file_path):
                try:
                    job_dpi = int(options.get("dpi", getattr(settings, "ocr_dpi", 300)))
                    logger.info(f"Converting PDF to images for job {job_id} at {job_dpi} DPI")
                    ocr_images = _pdf_to_images(
                        file_path,
                        batch_size=getattr(settings, "ocr_batch_size", 10),
                        dpi=job_dpi,
                    )
                    logger.info(f"PDF converted to {len(ocr_images)} page(s)")
                except ImportError as exc:
                    error_msg = "PDF rendering failed: Poppler is not installed. Please install poppler-utils (Linux/Windows) or poppler (macOS via Homebrew: brew install poppler)"
                    logger.error(error_msg, exc_info=True)
                    result["errors"].append(error_msg)
                except Exception as exc:
                    # Check if it's a Poppler-related error
                    if "poppler" in str(exc).lower() or "pdfinfonotinstalled" in str(type(exc).__name__).lower():
                        error_msg = f"PDF rendering failed: Poppler is not installed or not in PATH. Please install poppler-utils (Linux/Windows) or poppler (macOS via Homebrew: brew install poppler). Error: {exc}"
                    else:
                        error_msg = f"PDF rendering failed: {exc}"
                    logger.error(error_msg, exc_info=True)
                    result["errors"].append(error_msg)
            elif _is_image(file_path):
                logger.info(f"Processing image file for job {job_id}")
                ocr_images = [open_image(file_path)]
            else:
                result["errors"].append("Unsupported file type for OCR.")
            
            # Run OCR on all images (parallel page workers)
            ocr_page_pdfs = []
            if ocr_images:
                import gc
                total_pages = len(ocr_images)
                page_workers = getattr(settings, "ocr_page_workers", 2)

                # Compute a single options hash for all pages in this job
                page_opts_hash = (
                    hash_options(options, keys=_PAGE_OPTS_KEYS)
                    if cache is not None else None
                )
                logger.info(
                    f"Starting parallel OCR: {total_pages} page(s), "
                    f"{page_workers} worker(s), cache={'on' if cache else 'off'} "
                    f"for job {job_id}"
                )

                page_args_list = [
                    (idx, image, ocr_engine, lang, psm, oem, preprocess, is_scanned, cache, page_opts_hash)
                    for idx, image in enumerate(ocr_images, start=1)
                ]

                page_results = {}  # idx -> (ocr_text_dict, error_msg)
                completed_count = 0

                with _PageExecutor(max_workers=page_workers) as page_exec:
                    futures = {
                        page_exec.submit(_ocr_page_task, args): args[0]
                        for args in page_args_list
                    }
                    for future in _as_completed(futures):
                        if cancel_event and cancel_event.is_set():
                            logger.info(f"Job {job_id} cancelled during parallel OCR")
                            for f in futures:
                                f.cancel()
                            return

                        try:
                            idx, ocr_text, error_msg = future.result()
                        except Exception as exc:
                            idx = futures[future]
                            error_msg = f"Page {idx} OCR failed: {exc}"
                            ocr_text = {"text": "", "engine": ocr_engine, "detail": {"error": str(exc)}}

                        page_results[idx] = (ocr_text, error_msg)
                        if error_msg:
                            result["errors"].append(error_msg)

                        completed_count += 1
                        progress = int((completed_count / total_pages) * 100)
                        job_store.update_job(job_id, progress=progress)
                        logger.info(f"OCR page {idx}/{total_pages} done ({completed_count} completed)")

                        if total_pages > 50 and completed_count % 10 == 0:
                            gc.collect()
                            logger.info(f"Memory cleanup after {completed_count} completed pages")

                # Reassemble pages in document order
                for idx in range(1, total_pages + 1):
                    if idx not in page_results:
                        continue
                    ocr_text, _ = page_results[idx]
                    page_detail = ocr_text.get("detail", {}) or {}
                    page_pdf_bytes = page_detail.get("tesseract_pdf")
                    safe_detail = dict(page_detail)
                    safe_detail.pop("tesseract_pdf", None)
                    result["pages"].append({
                        "page": idx,
                        "text": ocr_text["text"],
                        "engine": ocr_text["engine"],
                        "detail": safe_detail,
                    })
                    ocr_page_pdfs.append(page_pdf_bytes)

                result["ocr_text"] = "\n\n".join(page["text"] for page in result["pages"])
                logger.info(f"OCR completed. Total text length: {len(result['ocr_text'])}")
                
                # For 'both' mode, extract text from OCR'd PDF
                if mode == "both":
                    result["final_text"] = result["ocr_text"]
                    logger.info(f"Text extraction enabled (mode=both)")
                else:
                    # For 'ocr' mode, no text extraction needed
                    result["final_text"] = ""
                    logger.info(f"Text extraction disabled (mode=ocr)")
            
            # Save results with PDF generation
            json_path, text_path, pdf_path = _persist_result(
                result,
                settings.result_dir,
                job_id,
                ocr_images,
                ocr_page_pdfs if ocr_images else None,
                generate_pdf=True,
            )
        
        else:
            result["errors"].append(f"Invalid mode: {mode}")
            json_path, text_path, pdf_path = _persist_result(
                result, settings.result_dir, job_id, ocr_images=[], generate_pdf=False
            )
        
        job_store.update_job(
            job_id,
            status="completed",
            result_path=json_path,
            text_path=text_path,
            pdf_path=pdf_path,
            progress=100,
        )
    except Exception as exc:
        result["errors"].append(str(exc))
        result["errors"].append(traceback.format_exc())
        json_path, text_path, pdf_path = _persist_result(
            result, settings.result_dir, job_id, [], generate_pdf=False
        )
        job_store.update_job(
            job_id,
            status="failed",
            result_path=json_path,
            text_path=text_path,
            pdf_path=pdf_path,
            error=str(exc),
            progress=100,
        )


def _run_ocr_engine(image, engine, result, lang="eng", psm=6, oem=1, preprocess="standard", deskew=True):
    """Run OCR engine on an image with error handling and logging.

    Args:
        image: PIL Image object or numpy array
        engine: OCR engine name ('tesseract' only)
        result: Result dictionary to append errors to
        lang: Tesseract language code
        psm: Tesseract page segmentation mode (default: 6)
        oem: Tesseract OCR engine mode (default: 1 — LSTM only)
        preprocess: Image preprocessing profile ("none", "standard", "aggressive")
        deskew: Whether to apply deskew correction (False for digital PDFs)

    Returns:
        Dictionary with 'text', 'engine', and 'detail' keys
    """
    try:
        logger.info(f"Running OCR with engine: {engine}, lang: {lang}, psm: {psm}, oem: {oem}, preprocess: {preprocess}, deskew: {deskew}")

        if engine != "tesseract":
            raise ValueError(f"Unsupported OCR engine: {engine}")
        ocr_result = run_tesseract(image, lang=lang, psm=psm, oem=oem, preprocess=preprocess, deskew=deskew)
        
        result_dict = ocr_result.__dict__
        logger.info(f"OCR completed. Engine: {engine}, Text length: {len(result_dict['text'])}, "
                   f"Detail: {result_dict.get('detail', {})}")
        
        return result_dict
    except Exception as exc:
        error_msg = f"OCR failed ({engine}): {exc}"
        logger.error(error_msg, exc_info=True)
        result["errors"].append(error_msg)
        return {"text": "", "engine": engine, "detail": {"error": str(exc)}}


def _persist_result(result, result_dir, job_id, ocr_images, ocr_page_pdfs=None, generate_pdf=True):
    """Save job results to disk.
    
    Args:
        result: Result dictionary with extracted text and metadata
        result_dir: Directory to save results
        job_id: Job identifier
        ocr_images: List of PIL images (for PDF generation with images)
        ocr_page_pdfs: Optional list of per-page PDF bytes (for Tesseract output)
        generate_pdf: Whether to generate a PDF file (False for text-only mode)
    
    Returns:
        Tuple of (json_path, text_path, pdf_path)
    """
    json_path, text_path, pdf_path = result_paths(result_dir, job_id)
    
    # Save JSON result
    with open(json_path, "w", encoding="utf-8") as handle:
        import json
        json.dump(result, handle, indent=2)
    
    # Save plain text
    with open(text_path, "w", encoding="utf-8") as handle:
        handle.write(result.get("final_text", ""))
    
    # Generate PDF output (only for OCR modes)
    if generate_pdf:
        try:
            if ocr_images and len(ocr_images) > 0:
                # Create PDF with images and text overlay (OCR modes only)
                page_texts = [page.get("text", "") for page in result.get("pages", [])]
                logger.info(f"Creating OCR PDF with {len(ocr_images)} images and {len(page_texts)} page texts")
                write_ocr_pdf_from_images(
                    pdf_path,
                    result.get("filename", "OCR Output"),
                    ocr_images,
                    page_texts,
                    ocr_page_pdfs,
                )
            else:
                # No images available - skip PDF generation
                logger.warning(f"No images available for PDF generation (mode might be text-only)")
                pdf_path = None
            
            # Verify PDF was created and has content
            import os
            if pdf_path and os.path.exists(pdf_path):
                pdf_size = os.path.getsize(pdf_path)
                logger.info(f"PDF created successfully: {pdf_path} ({pdf_size} bytes)")
                if pdf_size < 500:
                    logger.warning(f"PDF file is suspiciously small: {pdf_size} bytes")
            elif pdf_path:
                logger.error(f"PDF file was not created: {pdf_path}")
                
        except Exception as exc:
            logger.error(f"Failed to create PDF: {exc}", exc_info=True)
            pdf_path = None
    else:
        # Text-only mode - no PDF generation
        logger.info(f"PDF generation skipped (text-only mode)")
        pdf_path = None
    
    return json_path, text_path, pdf_path
