import json
import secrets
import sqlite3
import threading
from datetime import UTC, datetime


class JobStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists jobs (
                    id text primary key,
                    filename text,
                    status text,
                    created_at text,
                    updated_at text,
                    result_path text,
                    text_path text,
                    pdf_path text,
                    progress integer,
                    error text,
                    options text
                )
                """
            )
            conn.execute("pragma user_version;")
            version = conn.execute("pragma user_version;").fetchone()[0]
            if version < 1:
                try:
                    conn.execute("alter table jobs add column pdf_path text;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("pragma user_version = 1;")
            if version < 2:
                try:
                    conn.execute("alter table jobs add column progress integer default 0;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("pragma user_version = 2;")
            if version < 3:
                try:
                    conn.execute("alter table jobs add column image_path text;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("pragma user_version = 3;")
            if version < 4:
                try:
                    conn.execute("alter table jobs add column document_path text;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("pragma user_version = 4;")
            if version < 5:
                try:
                    conn.execute("alter table jobs add column audio_path text;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("pragma user_version = 5;")
            if version < 6:
                try:
                    conn.execute("alter table jobs add column video_path text;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("pragma user_version = 6;")
            if version < 7:
                conn.execute(
                    """
                    create table if not exists contact_submissions (
                        id integer primary key autoincrement,
                        name text not null,
                        email text not null,
                        subject text,
                        message text not null,
                        created_at text not null
                    )
                    """
                )
                conn.execute("pragma user_version = 7;")
            if version < 8:
                try:
                    conn.execute("alter table jobs add column session_id text;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("pragma user_version = 8;")
            if version < 9:
                try:
                    conn.execute("alter table jobs add column access_token text;")
                except sqlite3.OperationalError:
                    pass
                conn.execute("update jobs set access_token = hex(randomblob(16)) where access_token is null;")
                conn.execute("pragma user_version = 9;")
            if version < 10:
                try:
                    conn.execute("alter table jobs add column job_type text;")
                except sqlite3.OperationalError:
                    pass
                # Backfill job_type from the options JSON for existing rows
                conn.execute(
                    "update jobs set job_type = json_extract(options, '$.job_type') where job_type is null and options is not null;"
                )
                conn.execute("pragma user_version = 10;")

    def create_job(self, job_id, filename, options, session_id=None):
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        access_token = secrets.token_urlsafe(32)
        job_type = options.get("job_type") if isinstance(options, dict) else None
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                insert into jobs (id, filename, status, created_at, updated_at, progress, options, access_token, job_type)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, filename, "queued", now, now, 0, json.dumps(options), access_token, job_type),
            )
        return access_token

    def count_completed_jobs(self):
        with self._lock, self._connect() as conn:
            row = conn.execute("select count(*) from jobs where status='completed'").fetchone()
        return row[0] if row else 0

    def count_completed_by_type(self) -> dict:
        """Return a dict with total and per-type counts of completed jobs."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "select coalesce(job_type, 'unknown'), count(*) from jobs "
                "where status='completed' group by job_type"
            ).fetchall()
        counts = {row[0]: row[1] for row in rows}
        counts["total"] = sum(counts.values())
        return counts

    def update_job(self, job_id, **fields):
        fields["updated_at"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
        keys = ", ".join(f"{key}=?" for key in fields.keys())
        values = list(fields.values()) + [job_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"update jobs set {keys} where id=?", values)

    def get_job(self, job_id, access_token=None):
        with self._lock, self._connect() as conn:
            if access_token:
                row = conn.execute(
                    "select id, filename, status, created_at, updated_at, result_path, text_path, pdf_path, progress, error, options, image_path, document_path, audio_path, video_path "
                    "from jobs where id=? and access_token=?",
                    (job_id, access_token),
                ).fetchone()
            else:
                # For backward compatibility - allow internal access without token
                row = conn.execute(
                    "select id, filename, status, created_at, updated_at, result_path, text_path, pdf_path, progress, error, options, image_path, document_path, audio_path, video_path "
                    "from jobs where id=?",
                    (job_id,),
                ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "filename": row[1],
            "status": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "result_path": row[5],
            "text_path": row[6],
            "pdf_path": row[7],
            "progress": row[8] if row[8] is not None else 0,
            "error": row[9],
            "options": json.loads(row[10]) if row[10] else {},
            "image_path": row[11],
            "document_path": row[12],
            "audio_path": row[13],
            "video_path": row[14],
        }

    def delete_expired_jobs(self, cutoff_iso):
        """Delete jobs older than cutoff and return their file paths for cleanup."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "select id, result_path, text_path, pdf_path, image_path, document_path, audio_path, video_path "
                "from jobs where created_at < ? and status in ('completed', 'failed')",
                (cutoff_iso,),
            ).fetchall()
            if rows:
                ids = [r[0] for r in rows]
                conn.execute(
                    f"delete from jobs where id in ({','.join('?' * len(ids))})",
                    ids,
                )
        paths = []
        for row in rows:
            paths.extend(p for p in row[1:] if p)
        return [r[0] for r in rows], paths

    def delete_jobs_by_ids(self, job_ids):
        """Delete specific jobs by ID and return their file paths for cleanup."""
        if not job_ids:
            return [], []
        placeholders = ",".join("?" * len(job_ids))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"select id, result_path, text_path, pdf_path, image_path, document_path, audio_path, video_path "
                f"from jobs where id in ({placeholders})",
                job_ids,
            ).fetchall()
            if rows:
                ids = [r[0] for r in rows]
                conn.execute(
                    f"delete from jobs where id in ({','.join('?' * len(ids))})",
                    ids,
                )
        paths = []
        for row in rows:
            paths.extend(p for p in row[1:] if p)
        return [r[0] for r in rows], paths

    def list_recent_jobs(self, limit=50, session_id=None):
        with self._lock, self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    "select id, filename, status, created_at, updated_at, progress, options "
                    "from jobs where session_id = ? order by created_at desc limit ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "select id, filename, status, created_at, updated_at, progress, options "
                    "from jobs order by created_at desc limit ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id": row[0],
                "filename": row[1],
                "status": row[2],
                "created_at": row[3],
                "updated_at": row[4],
                "progress": row[5] if row[5] is not None else 0,
                "options": json.loads(row[6]) if row[6] else {},
            }
            for row in rows
        ]

    def save_contact_submission(self, name, email, subject, message):
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                insert into contact_submissions (name, email, subject, message, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (name, email, subject, message, now),
            )
            return True
