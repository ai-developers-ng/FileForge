import os


class Settings:
    def __init__(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.base_dir = base_dir
        self.data_dir = os.path.join(base_dir, "data")
        self.upload_dir = os.path.join(self.data_dir, "uploads")
        self.result_dir = os.path.join(self.data_dir, "results")
        self.db_path = os.path.join(self.data_dir, "jobs.db")
        self.tika_url = os.environ.get("TIKA_SERVER_URL", "http://localhost:9998")
        self.max_file_mb = int(os.environ.get("MAX_FILE_MB", "25"))
        self.cleanup_ttl_hours = int(os.environ.get("CLEANUP_TTL_HOURS", "24"))
        self.cleanup_interval_minutes = int(os.environ.get("CLEANUP_INTERVAL_MINUTES", "30"))
        self.worker_count = int(os.environ.get("WORKER_COUNT", "2"))
        self.ocr_dpi = int(os.environ.get("OCR_DPI", "300"))
        # DEPRECATED: No longer used - mode selection is explicit (text/ocr/both)
        self.ocr_text_threshold = int(os.environ.get("OCR_TEXT_THRESHOLD", "50"))
