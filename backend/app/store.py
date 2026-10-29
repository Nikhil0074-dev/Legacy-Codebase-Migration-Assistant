"""SQLite job store (JSON documents). Originals are never mutated."""
import json
import sqlite3
import threading


class Store:
    def __init__(self, path=":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, seq INTEGER, doc TEXT NOT NULL)")
            self._db.commit()

    def save(self, job: dict):
        with self._lock:
            row = self._db.execute("SELECT seq FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if row is None:
                n = self._db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM jobs").fetchone()[0]
                self._db.execute("INSERT INTO jobs VALUES (?,?,?)", (job["id"], n, json.dumps(job)))
            else:
                self._db.execute("UPDATE jobs SET doc=? WHERE id=?", (json.dumps(job), job["id"]))
            self._db.commit()

    def get(self, job_id):
        with self._lock:
            row = self._db.execute("SELECT doc FROM jobs WHERE id=?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self):
        with self._lock:
            rows = self._db.execute("SELECT doc FROM jobs ORDER BY seq DESC").fetchall()
        return [json.loads(r[0]) for r in rows]
