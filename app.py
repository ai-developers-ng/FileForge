import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

from ocr_engine.audio_pipeline import process_audio_job
from ocr_engine.cleanup import start_cleanup_thread
from ocr_engine.config import Settings
from ocr_engine.document_pipeline import process_document_job
from ocr_engine.image_pipeline import process_image_job
from ocr_engine.jobs import JobStore
from ocr_engine.pdf_pipeline import process_pdf_job
from ocr_engine.pipeline import process_job
from ocr_engine.storage import ensure_dirs
from ocr_engine.video_pipeline import process_video_job


MIME_TO_EXT = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/gif": {".gif"},
    "image/bmp": {".bmp"},
    "image/tiff": {".tif", ".tiff"},
    "image/webp": {".webp"},
    "image/svg+xml": {".svg", ".svgz"},
    "image/x-icon": {".ico"},
    "audio/mpeg": {".mp3", ".mp2"},
    "audio/wav": {".wav"},
    "audio/x-wav": {".wav"},
    "audio/flac": {".flac"},
    "audio/ogg": {".ogg", ".oga", ".opus"},
    "audio/aac": {".aac"},
    "audio/mp4": {".m4a", ".m4b"},
    "video/mp4": {".mp4", ".m4v"},
    "video/x-matroska": {".mkv"},
    "video/webm": {".webm"},
    "video/x-msvideo": {".avi"},
    "video/quicktime": {".mov"},
    "text/html": {".html", ".htm"},
    "text/plain": {".txt", ".md", ".csv", ".tsv", ".rst"},
    "text/csv": {".csv"},
    "text/xml": {".xml", ".docbook"},
    "application/json": {".json"},
    "application/epub+zip": {".epub"},
    "application/rtf": {".rtf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.oasis.opendocument.text": {".odt"},
}


def _validate_magic(file_path, ext):
    """Validate file content matches its extension using magic bytes.
    Returns True if valid or if magic is unavailable, False if mismatch."""
    try:
        import magic
        detected_mime = magic.from_file(file_path, mime=True)
    except (ImportError, Exception):
        return True  # Skip validation if python-magic not available

    allowed_exts = MIME_TO_EXT.get(detected_mime)
    if allowed_exts is None:
        return True  # Unknown MIME type, allow
    return ext in allowed_exts


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "fileforge-dev-key-change-in-production")
    if os.environ.get("FLASK_ENV") == "production" and app.secret_key == "fileforge-dev-key-change-in-production":
        raise RuntimeError("SECRET_KEY must be set in production. Set the SECRET_KEY environment variable.")
    limiter = Limiter(get_remote_address, app=app, storage_uri="memory://", default_limits=[])
    csrf = CSRFProtect(app)
    compress = Compress(app)
    settings = Settings()
    ensure_dirs(settings.data_dir, settings.upload_dir, settings.result_dir)
    job_store = JobStore(settings.db_path)
    executor = ThreadPoolExecutor(max_workers=settings.worker_count)
    start_cleanup_thread(settings, job_store)

    @app.before_request
    def ensure_session_id():
        if "sid" not in session:
            session["sid"] = str(uuid.uuid4())
            session.permanent = True

    @app.context_processor
    def inject_now():
        return {"now": datetime.now(UTC)}
    ocr_ext = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
    # ImageMagick supported formats (via Wand)
    image_ext = {
        # Common formats
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".ico",
        # Modern formats
        ".heic", ".heif", ".avif", ".jxl",
        # Vector/special
        ".svg", ".svgz", ".eps", ".pdf", ".psd", ".xcf",
        # RAW camera formats
        ".nef", ".cr2", ".cr3", ".arw", ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw", ".raw",
        # Other formats
        ".hdr", ".exr", ".tga", ".pcx", ".ppm", ".pgm", ".pbm", ".pnm", ".ico", ".cur",
        ".dds", ".jp2", ".j2k", ".jpc", ".jpx", ".mng", ".jng", ".wbmp", ".xbm", ".xpm",
    }
    # Document formats (via Pandoc)
    document_ext = {
        ".docx", ".doc", ".md", ".html", ".htm", ".rtf",
        ".csv", ".tsv", ".json", ".rst", ".epub", ".odt", ".docbook", ".xml", ".txt",
    }
    # Audio/video formats (via pydub/FFmpeg)
    audio_ext = {
        # Audio formats
        ".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus", ".aac", ".m4a",
        ".wma", ".amr", ".ac3", ".aiff", ".aifc", ".aif", ".mp2", ".au",
        ".m4b", ".voc", ".weba", ".alac", ".caf", ".mpc", ".mogg",
        # Video formats (extract audio)
        ".mp4", ".mkv", ".avi", ".mov", ".webm", ".ts", ".mts", ".m2ts",
        ".wmv", ".mpg", ".mpeg", ".flv", ".f4v", ".vob", ".m4v", ".3gp",
        ".3g2", ".mxf", ".ogv", ".rm", ".rmvb", ".divx",
    }
    # Video formats (via FFmpeg)
    video_ext = {
        ".mkv", ".mp4", ".webm", ".avi", ".wmv", ".mov", ".gif",
        ".mts", ".ts", ".m2ts", ".mpg", ".mpeg", ".flv", ".f4v",
        ".vob", ".m4v", ".3gp", ".3g2", ".mxf", ".ogv", ".rm",
        ".rmvb", ".h264", ".divx", ".swf", ".amv", ".asf", ".nut",
    }

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/results/<job_id>")
    def result_page(job_id):
        job = job_store.get_job(job_id)
        if not job:
            return redirect(url_for("index"))
        return render_template("result.html", job=job)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({"error": "rate limit exceeded", "message": str(e.description)}), 429

    @app.route("/api/jobs", methods=["POST"])
    @limiter.limit("20/minute")
    def create_job():
        if "file" not in request.files:
            return jsonify({"error": "file is required"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "file is required"}), 400

        max_bytes = settings.max_file_mb * 1024 * 1024
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > max_bytes:
            return jsonify({"error": f"file exceeds {settings.max_file_mb} MB"}), 400

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        job_type = request.form.get("job_type", "ocr")

        # Validate extension based on job type
        if job_type == "image":
            if ext not in image_ext:
                return jsonify({"error": "unsupported file type for image conversion"}), 400
        elif job_type == "document":
            if ext not in document_ext:
                return jsonify({"error": "unsupported file type for document conversion"}), 400
        elif job_type == "audio":
            if ext not in audio_ext:
                return jsonify({"error": "unsupported file type for audio conversion"}), 400
        elif job_type == "video":
            if ext not in video_ext:
                return jsonify({"error": "unsupported file type for video conversion"}), 400
        else:
            if ext not in ocr_ext:
                return jsonify({"error": "unsupported file type"}), 400

        job_id = str(uuid.uuid4())
        upload_path = os.path.join(settings.upload_dir, f"{job_id}-{filename}")
        file.save(upload_path)

        if not _validate_magic(upload_path, ext):
            os.remove(upload_path)
            return jsonify({"error": "file content does not match its extension"}), 400

        if job_type == "image":
            options = {
                "job_type": "image",
                "output_format": request.form.get("output_format", "png"),
                "quality": request.form.get("quality", "85"),
                "resize_width": request.form.get("resize_width"),
                "resize_height": request.form.get("resize_height"),
                "resize_percent": request.form.get("resize_percent"),
                "dpi": request.form.get("dpi"),
                "grayscale": request.form.get("grayscale") == "true",
                "rotation": request.form.get("rotation", "0"),
                "brightness": request.form.get("brightness", "1.0"),
                "contrast": request.form.get("contrast", "1.0"),
            }
            job_store.create_job(job_id, filename, options, session_id=session.get("sid"))
            executor.submit(process_image_job, job_id, upload_path, options, settings, job_store)
        elif job_type == "document":
            options = {
                "job_type": "document",
                "output_format": request.form.get("output_format", "pdf"),
            }
            job_store.create_job(job_id, filename, options, session_id=session.get("sid"))
            executor.submit(process_document_job, job_id, upload_path, options, settings, job_store)
        elif job_type == "audio":
            options = {
                "job_type": "audio",
                "output_format": request.form.get("output_format", "mp3"),
                "bitrate": request.form.get("bitrate", "192"),
            }
            job_store.create_job(job_id, filename, options, session_id=session.get("sid"))
            executor.submit(process_audio_job, job_id, upload_path, options, settings, job_store)
        elif job_type == "video":
            options = {
                "job_type": "video",
                "output_format": request.form.get("output_format", "mp4"),
                "quality": request.form.get("quality", "medium"),
            }
            job_store.create_job(job_id, filename, options, session_id=session.get("sid"))
            executor.submit(process_video_job, job_id, upload_path, options, settings, job_store)
        else:
            options = {
                "job_type": "ocr",
                "mode": request.form.get("mode", "text"),
                "ocr_engine": request.form.get("ocr_engine", "tesseract"),
                "lang": request.form.get("lang", "eng"),
            }
            job_store.create_job(job_id, filename, options, session_id=session.get("sid"))
            executor.submit(process_job, job_id, upload_path, options, settings, job_store)

        return jsonify(
            {
                "job_id": job_id,
                "status": "queued",
                "result_url": url_for("get_job_result", job_id=job_id),
            }
        )

    @app.route("/api/pdf-jobs", methods=["POST"])
    @limiter.limit("20/minute")
    def create_pdf_job():
        files = request.files.getlist("files")
        if not files or len(files) == 0:
            return jsonify({"error": "at least one file is required"}), 400

        pdf_mode = request.form.get("pdf_mode", "merge")
        max_bytes = settings.max_file_mb * 1024 * 1024

        # Images-to-PDF accepts image files; everything else requires PDFs
        image_mode = pdf_mode == "from_images"
        allowed_image_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}

        saved_paths = []
        job_id = str(uuid.uuid4())
        for file in files:
            if file.filename == "":
                continue
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower()
            if image_mode:
                if ext not in allowed_image_exts:
                    for p in saved_paths:
                        os.remove(p)
                    return jsonify({"error": "only image files (PNG, JPG, GIF, BMP, TIFF, WebP) are accepted for this tool"}), 400
            else:
                if ext != ".pdf":
                    for p in saved_paths:
                        os.remove(p)
                    return jsonify({"error": "only PDF files are accepted"}), 400
            file.seek(0, os.SEEK_END)
            if file.tell() > max_bytes:
                for p in saved_paths:
                    os.remove(p)
                return jsonify({"error": f"file exceeds {settings.max_file_mb} MB"}), 400
            file.seek(0)
            path = os.path.join(settings.upload_dir, f"{job_id}-{filename}")
            file.save(path)
            saved_paths.append(path)

        if not saved_paths:
            return jsonify({"error": "no valid files uploaded"}), 400

        if pdf_mode == "merge" and len(saved_paths) < 2:
            for p in saved_paths:
                os.remove(p)
            return jsonify({"error": "merge requires at least 2 PDF files"}), 400

        options = {"job_type": "pdf", "pdf_mode": pdf_mode}

        # Pass tool-specific options
        if pdf_mode == "rotate":
            options["rotate_degrees"] = request.form.get("rotate_degrees", "90")
        elif pdf_mode in ("extract", "delete"):
            options["page_range"] = request.form.get("page_range", "1")
        elif pdf_mode == "watermark":
            options["watermark_text"] = request.form.get("watermark_text", "WATERMARK")
            options["watermark_opacity"] = request.form.get("watermark_opacity", "0.3")
            options["watermark_font_size"] = request.form.get("watermark_font_size", "60")
            options["watermark_rotation"] = request.form.get("watermark_rotation", "45")
        elif pdf_mode in ("protect", "unlock"):
            options["password"] = request.form.get("password", "")
        elif pdf_mode == "to_images":
            options["image_format"] = request.form.get("image_format", "png")
            options["dpi"] = request.form.get("dpi", "200")
        elif pdf_mode == "page_numbers":
            options["number_position"] = request.form.get("number_position", "bottom-center")
            options["start_number"] = request.form.get("start_number", "1")
        elif pdf_mode == "metadata":
            options["meta_title"] = request.form.get("meta_title", "")
            options["meta_author"] = request.form.get("meta_author", "")
            options["meta_subject"] = request.form.get("meta_subject", "")
            options["meta_keywords"] = request.form.get("meta_keywords", "")

        first_filename = secure_filename(files[0].filename)
        job_store.create_job(job_id, first_filename, options, session_id=session.get("sid"))
        executor.submit(process_pdf_job, job_id, saved_paths, options, settings, job_store)

        return jsonify({"job_id": job_id, "status": "queued"})

    @app.route("/api/jobs/<job_id>", methods=["GET"])
    def get_job(job_id):
        job = job_store.get_job(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job)

    @app.route("/api/jobs/<job_id>/stream", methods=["GET"])
    def stream_job(job_id):
        def generate():
            while True:
                job = job_store.get_job(job_id)
                if not job:
                    yield f"data: {json.dumps({'error': 'job not found'})}\n\n"
                    return
                payload = {
                    "status": job["status"],
                    "progress": job.get("progress", 0),
                    "error": job.get("error"),
                }
                yield f"data: {json.dumps(payload)}\n\n"
                if job["status"] in ("completed", "failed"):
                    return
                time.sleep(1)

        return Response(generate(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        })

    @app.route("/api/jobs/<job_id>/result", methods=["GET"])
    def get_job_result(job_id):
        job = job_store.get_job(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        if job["status"] not in ("completed", "failed"):
            return jsonify({"status": job["status"]}), 202
        if not job["result_path"]:
            return jsonify({"error": "result not available"}), 404
        with open(job["result_path"], "r", encoding="utf-8") as handle:
            return jsonify(json.load(handle))

    @app.route("/api/jobs/<job_id>/download/<fmt>", methods=["GET"])
    def download_result(job_id, fmt):
        job = job_store.get_job(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404

        # Use original filename with _OCR suffix
        original_name = os.path.splitext(job.get("filename", job_id))[0]
        base_name = f"{original_name}_OCR"

        if fmt == "txt":
            if job["text_path"] and os.path.exists(job["text_path"]):
                return send_file(job["text_path"], as_attachment=True, download_name=f"{base_name}.txt")
            return jsonify({"error": "text file not available"}), 404

        if fmt == "json":
            if job["result_path"] and os.path.exists(job["result_path"]):
                return send_file(job["result_path"], as_attachment=True, download_name=f"{base_name}.json")
            return jsonify({"error": "json file not available"}), 404

        if fmt == "pdf":
            if job.get("pdf_path") and os.path.exists(job["pdf_path"]):
                pdf_path = job["pdf_path"]
                if pdf_path.endswith(".zip"):
                    return send_file(pdf_path, as_attachment=True, download_name=f"{original_name}_split.zip")
                return send_file(pdf_path, as_attachment=True, download_name=f"{base_name}.pdf")
            return jsonify({"error": "PDF not available for this processing mode"}), 404

        if fmt == "image":
            options = job.get("options", {})
            if options.get("job_type") != "image":
                return jsonify({"error": "not an image conversion job"}), 400
            image_path = job.get("image_path")
            if not image_path or not os.path.exists(image_path):
                return jsonify({"error": "converted image not available"}), 404
            output_format = options.get("output_format", "png")
            original_name = os.path.splitext(job.get("filename", job_id))[0]
            download_name = f"{original_name}_converted.{output_format}"
            return send_file(image_path, as_attachment=True, download_name=download_name)

        if fmt == "document":
            options = job.get("options", {})
            if options.get("job_type") != "document":
                return jsonify({"error": "not a document conversion job"}), 400
            document_path = job.get("document_path")
            if not document_path or not os.path.exists(document_path):
                return jsonify({"error": "converted document not available"}), 404
            output_format = options.get("output_format", "pdf")
            original_name = os.path.splitext(job.get("filename", job_id))[0]
            download_name = f"{original_name}_converted.{output_format}"
            return send_file(document_path, as_attachment=True, download_name=download_name)

        if fmt == "audio":
            options = job.get("options", {})
            if options.get("job_type") != "audio":
                return jsonify({"error": "not an audio conversion job"}), 400
            audio_path = job.get("audio_path")
            if not audio_path or not os.path.exists(audio_path):
                return jsonify({"error": "converted audio not available"}), 404
            output_format = options.get("output_format", "mp3")
            original_name = os.path.splitext(job.get("filename", job_id))[0]
            download_name = f"{original_name}_converted.{output_format}"
            return send_file(audio_path, as_attachment=True, download_name=download_name)

        if fmt == "video":
            options = job.get("options", {})
            if options.get("job_type") != "video":
                return jsonify({"error": "not a video conversion job"}), 400
            video_path = job.get("video_path")
            if not video_path or not os.path.exists(video_path):
                return jsonify({"error": "converted video not available"}), 404
            output_format = options.get("output_format", "mp4")
            original_name = os.path.splitext(job.get("filename", job_id))[0]
            download_name = f"{original_name}_converted.{output_format}"
            return send_file(video_path, as_attachment=True, download_name=download_name)

        return jsonify({"error": "unsupported format"}), 400

    @app.route("/history")
    def history():
        jobs = job_store.list_recent_jobs(limit=50, session_id=session.get("sid"))
        return render_template("history.html", jobs=jobs)

    @app.route("/docs")
    def docs():
        return render_template("docs.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            if request.form.get("website"):
                flash("Thank you for your message! We'll get back to you soon.", "success")
                return redirect(url_for("contact"))

            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            subject = request.form.get("subject", "").strip()
            message = request.form.get("message", "").strip()

            if not name or not email or not message:
                flash("Please fill in all required fields.", "error")
                return render_template("contact.html")

            try:
                job_store.save_contact_submission(name, email, subject, message)
                flash("Thank you for your message! We'll get back to you soon.", "success")
                return redirect(url_for("contact"))
            except Exception:
                flash("An error occurred. Please try again.", "error")

        return render_template("contact.html")

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/robots.txt")
    def robots():
        content = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /results/

Sitemap: {host}sitemap.xml
""".format(host=request.host_url)
        return Response(content, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap():
        return render_template("sitemap.xml"), 200, {"Content-Type": "application/xml"}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
