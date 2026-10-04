import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DETAIL_FIELDS = {"prompt", "raw_response", "attempts", "workflow"}


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

    def delete_document(self, doc_id):
        with self.connect() as db:
            db.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
            db.execute("DELETE FROM documents WHERE id=?", (doc_id,))

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

    def runs(self, limit=100, offset=0):
        with self.connect() as db:
            rows = db.execute(
                "SELECT data FROM runs ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        # Prompts/raw completions belong to the detail endpoint, not every list refresh.
        return [
            {k: v for k, v in json.loads(row[0]).items() if k not in DETAIL_FIELDS} for row in rows
        ]

    def run_catalog(self, search="", status="", offset=0, limit=50):
        # instr treats user text literally, including SQL LIKE wildcard characters.
        where = "WHERE instr(lower(json_extract(data, '$.question')), lower(?)) > 0"
        args = [search]
        if status:
            where += " AND json_extract(data, '$.status')=?"
            args.append(status)
        with self.connect() as db:
            total = db.execute("SELECT count(*) FROM runs").fetchone()[0]
            matched = db.execute(f"SELECT count(*) FROM runs {where}", args).fetchone()[0]
            rows = db.execute(
                f"SELECT data FROM runs {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                [*args, limit, offset],
            ).fetchall()
        items = [
            {k: v for k, v in json.loads(row[0]).items() if k not in DETAIL_FIELDS} for row in rows
        ]
        return {
            "items": items,
            "total": total,
            "matched": matched,
            "offset": offset,
            "limit": limit,
        }

    def run_states(self):
        with self.connect() as db:
            return dict(
                db.execute("SELECT id, json_extract(data, '$.status') FROM runs").fetchall()
            )

    def delete_runs(self, run_ids):
        with self.connect() as db:
            db.executemany("DELETE FROM runs WHERE id=?", [(rid,) for rid in run_ids])

    def recover_interrupted(self):
        for doc in self.documents():
            if doc["status"] == "deleting":
                doc.update(status="delete_failed", error="清理被服務重啟中斷，請重試刪除文件。")
                self.save_document(doc)
            elif doc["status"] not in {"ready", "failed", "cancelled", "delete_failed"}:
                doc.update(
                    status="failed",
                    error="處理被服務重啟中斷，請按重新索引。",
                    error_code="interrupted",
                    finished_at=now(),
                )
                self.save_document(doc)
        for run_id, status in self.run_states().items():
            if status == "running":
                full = self.run(run_id)
                full.update(
                    status="failed",
                    stage="failed",
                    error_code="interrupted",
                    finished_at=now(),
                    error="工作流程被服務重啟中斷，請重新送出。",
                )
                for attempt in full.get("attempts", []):
                    if (
                        attempt["status"] == "running"
                        and "usage" in full
                        and not {"actual_input_tokens", "actual_output_tokens"}
                        <= attempt.get("context", {}).keys()
                    ):
                        full["usage"]["unreported_calls"] += 1
                for record in [
                    *full.get("attempts", []),
                    *full.get("workflow", {}).get("nodes", []),
                ]:
                    if record["status"] == "running":
                        record.update(status="failed", error_code="interrupted", finished_at=now())
                self.save_run(full)
