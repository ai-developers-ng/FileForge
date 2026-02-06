import json
import sqlite3
import threading
from datetime import datetime


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

    def create_job(self, job_id, filename, options):
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                insert into jobs (id, filename, status, created_at, updated_at, progress, options)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, filename, "queued", now, now, 0, json.dumps(options)),
            )

    def update_job(self, job_id, **fields):
        fields["updated_at"] = datetime.utcnow().isoformat()
        keys = ", ".join(f"{key}=?" for key in fields.keys())
        values = list(fields.values()) + [job_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"update jobs set {keys} where id=?", values)

    def get_job(self, job_id):
        with self._lock, self._connect() as conn:
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

    def save_contact_submission(self, name, email, subject, message):
        now = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                insert into contact_submissions (name, email, subject, message, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (name, email, subject, message, now),
            )
            return True
