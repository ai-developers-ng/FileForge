import glob
import logging
import os
import threading
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


def _run_cleanup(settings, job_store):
    cutoff = (datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=settings.cleanup_ttl_hours)).isoformat()
    job_ids, db_paths = job_store.delete_expired_jobs(cutoff)

    removed = 0
    # Remove files tracked in the database
    for path in db_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                removed += 1
        except OSError:
            logger.warning("failed to remove %s", path)

    # Remove upload files for those jobs (pattern: <job_id>-<filename>)
    for job_id in job_ids:
        for path in glob.glob(os.path.join(settings.upload_dir, f"{job_id}-*")):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                logger.warning("failed to remove %s", path)

    if job_ids:
        logger.info("cleanup: removed %d jobs, %d files", len(job_ids), removed)


def start_cleanup_thread(settings, job_store):
    def loop():
        while True:
            try:
                _run_cleanup(settings, job_store)
            except Exception:
                logger.exception("cleanup error")
            event.wait(settings.cleanup_interval_minutes * 60)
            if event.is_set():
                break

    event = threading.Event()
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
