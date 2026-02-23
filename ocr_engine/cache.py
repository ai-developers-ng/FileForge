"""OCR result cache — page-level and file-level.

Two cache layers backed by a single SQLite database:

  page_cache  — keyed by (SHA-256 of image PNG, options hash)
                stores Tesseract text + confidence + PDF bytes
                hit = zero Tesseract subprocess calls for that page

  file_cache  — keyed by (SHA-256 of file bytes, options hash)
                stores Tika text-extraction results (text-only mode)
                hit = zero Tika round-trips for that file

Both tables use LRU eviction when they exceed their configured limits.
"""

import hashlib
import io
import json
import logging
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Options keys that affect OCR output (used to build cache keys)
_PAGE_OPTS_KEYS = ("ocr_engine", "lang", "psm", "oem", "preprocess")
_FILE_OPTS_KEYS = ("mode",)


def hash_file(file_path: str) -> str:
    """Return SHA-256 hex digest of a file (chunked — safe for large files)."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_image(image) -> str:
    """Return SHA-256 hex digest of a PIL Image serialised as PNG bytes."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return hashlib.sha256(buf.getvalue()).hexdigest()


def hash_options(options: dict, keys=_PAGE_OPTS_KEYS) -> str:
    """Return a stable 16-char hex hash of the specified option keys."""
    canonical = {k: str(options.get(k, "")) for k in keys}
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True).encode()
    ).hexdigest()[:16]


class OcrCache:
    """SQLite-backed LRU cache for Tesseract (page) and Tika (file) results."""

    def __init__(
        self,
        db_path: str,
        max_file_entries: int = 500,
        max_page_entries: int = 10000,
    ):
        self.db_path = db_path
        self.max_file_entries = max_file_entries
        self.max_page_entries = max_page_entries
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS page_cache (
                    cache_key   TEXT PRIMARY KEY,
                    ocr_text    TEXT NOT NULL,
                    confidence  REAL,
                    pdf_bytes   BLOB,
                    created_at  TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    hit_count   INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_cache (
                    cache_key   TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    hit_count   INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_accessed "
                "ON page_cache(accessed_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_accessed "
                "ON file_cache(accessed_at)"
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).replace(tzinfo=None).isoformat()

    # ── Page-level cache (Tesseract per-image) ────────────────────────────────

    def get_page(self, image_hash: str, options_hash: str) -> Optional[dict]:
        """Return cached OCR result dict, or None on a miss."""
        key = f"p:{image_hash}:{options_hash}"
        now = self._now()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT ocr_text, confidence, pdf_bytes "
                "FROM page_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE page_cache "
                    "SET accessed_at = ?, hit_count = hit_count + 1 "
                    "WHERE cache_key = ?",
                    (now, key),
                )
                detail: dict = {"confidence": row[1]}
                if row[2]:
                    detail["tesseract_pdf"] = bytes(row[2])
                logger.debug("Page cache HIT: %s…", key[:40])
                return {"text": row[0], "engine": "tesseract", "detail": detail}
        return None

    def set_page(self, image_hash: str, options_hash: str, ocr_result: dict) -> None:
        """Store an OCR result in the page cache."""
        key = f"p:{image_hash}:{options_hash}"
        now = self._now()
        detail = ocr_result.get("detail", {}) or {}
        text = ocr_result.get("text", "")
        confidence = detail.get("confidence")
        pdf_bytes = detail.get("tesseract_pdf")  # bytes or None
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO page_cache "
                "(cache_key, ocr_text, confidence, pdf_bytes, "
                " created_at, accessed_at, hit_count) "
                "VALUES (?, ?, ?, ?, ?, ?, 0)",
                (key, text, confidence, pdf_bytes, now, now),
            )
        self._evict("page_cache", self.max_page_entries)
        logger.debug("Page cache SET: %s…", key[:40])

    # ── File-level cache (Tika text-only mode) ────────────────────────────────

    def get_file(self, file_hash: str, options_hash: str) -> Optional[dict]:
        """Return cached Tika extraction result dict, or None on a miss."""
        key = f"f:{file_hash}:{options_hash}"
        now = self._now()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM file_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE file_cache "
                    "SET accessed_at = ?, hit_count = hit_count + 1 "
                    "WHERE cache_key = ?",
                    (now, key),
                )
                logger.info("File cache HIT: %s…", key[:40])
                return json.loads(row[0])
        return None

    def set_file(self, file_hash: str, options_hash: str, result: dict) -> None:
        """Store a Tika extraction result in the file cache."""
        key = f"f:{file_hash}:{options_hash}"
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO file_cache "
                "(cache_key, result_json, created_at, accessed_at, hit_count) "
                "VALUES (?, ?, ?, ?, 0)",
                (key, json.dumps(result), now, now),
            )
        self._evict("file_cache", self.max_file_entries)
        logger.info("File cache SET: %s…", key[:40])

    # ── Stats (for logging / admin) ───────────────────────────────────────────

    def stats(self) -> dict:
        """Return hit counts and entry counts for both tables."""
        with self._lock, self._connect() as conn:
            pc = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM page_cache"
            ).fetchone()
            fc = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM file_cache"
            ).fetchone()
        return {
            "page_entries": pc[0],
            "page_hits": pc[1],
            "file_entries": fc[0],
            "file_hits": fc[1],
        }

    # ── LRU eviction ─────────────────────────────────────────────────────────

    def _evict(self, table: str, max_entries: int) -> None:
        with self._lock, self._connect() as conn:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count > max_entries:
                excess = count - max_entries
                conn.execute(
                    f"DELETE FROM {table} WHERE cache_key IN "
                    f"(SELECT cache_key FROM {table} "
                    f" ORDER BY accessed_at ASC LIMIT ?)",
                    (excess,),
                )
                logger.info("Evicted %d entries from %s", excess, table)
