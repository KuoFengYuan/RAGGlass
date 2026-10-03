import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def now():
    return datetime.now(UTC).isoformat()


class Store:
    """SQLite metadata is the source of truth; vectors can be rebuilt from chunks."""

    def __init__(self, directory: Path):
        self.directory = directory
        (directory / "documents").mkdir(parents=True, exist_ok=True)
        self.path = directory / "ragglass.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, hash TEXT UNIQUE NOT NULL, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL, data TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL
                );
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def save_document(self, doc):
        with self.connect() as db:
            db.execute(
                "INSERT INTO documents VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (doc["id"], doc["hash"], json.dumps(doc, ensure_ascii=False)),
            )

    def document(self, doc_id):
        with self.connect() as db:
            row = db.execute("SELECT data FROM documents WHERE id=?", (doc_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def by_hash(self, digest):
        with self.connect() as db:
            row = db.execute("SELECT data FROM documents WHERE hash=?", (digest,)).fetchone()
        return json.loads(row[0]) if row else None

    def documents(self):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM documents ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_chunks(self, doc_id, chunks):
        with self.connect() as db:
            db.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
            db.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?)",
                [(c["id"], doc_id, json.dumps(c, ensure_ascii=False)) for c in chunks],
            )

    def chunks(self, doc_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT data FROM chunks WHERE document_id=? ORDER BY rowid", (doc_id,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_run(self, run):
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (run["id"], run["created_at"], json.dumps(run, ensure_ascii=False)),
            )

    def run(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def runs(self, limit=100):
        with self.connect() as db:
            rows = db.execute(
                "SELECT data FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        # Prompts/raw completions belong to the detail endpoint, not every list refresh.
        return [
            {k: v for k, v in json.loads(row[0]).items() if k not in {"prompt", "raw_response"}}
            for row in rows
        ]

    def recover_interrupted(self):
        for doc in self.documents():
            if doc["status"] not in {"ready", "failed"}:
                doc.update(status="failed", error="處理被服務重啟中斷，請按重新索引。")
                self.save_document(doc)
        for run in self.runs():
            if run["status"] == "running":
                full = self.run(run["id"])
                full.update(status="failed", error="查詢被服務重啟中斷，請重新送出問題。")
                self.save_run(full)
