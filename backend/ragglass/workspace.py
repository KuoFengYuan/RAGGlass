"""Coordinate destructive changes with active work in this single-worker application."""

import shutil
import threading
import uuid
from collections import Counter
from contextlib import contextmanager

from .errors import PipelineError
from .store import now


class Workspace:
    def __init__(self, store, index):
        self.store = store
        self.index = index
        self.lock = threading.Lock()
        self.active_documents = Counter()
        self.active_queries = 0

    @contextmanager
    def mutation(self):
        if not self.lock.acquire(blocking=False):
            raise PipelineError("workspace_busy", "工作空間正在更新，請稍後重試。", 409)
        try:
            yield
        finally:
            self.lock.release()

    @contextmanager
    def activity(self, document_ids, query=False, wait=True):
        # Queued ingestion must wait for an unrelated cleanup rather than fail to start.
        if not self.lock.acquire(blocking=wait):
            raise PipelineError("workspace_busy", "工作空間正在更新，請稍後重試。", 409)
        try:
            self.active_documents.update(document_ids)
            self.active_queries += int(query)
        finally:
            self.lock.release()
        try:
            yield
        finally:
            with self.lock:
                self.active_documents.subtract(document_ids)
                self.active_queries -= int(query)

    def cleanup(self, kind, ids=(), all_items=False, expected_count=None):
        with self.mutation():
            documents = {d["id"]: d for d in self.store.documents()}
            records = documents if kind == "documents" else self.store.run_states()
            if all_items and expected_count != len(records):
                raise PipelineError(
                    "cleanup_count_changed", "資料數量已變更，請重新整理後再次確認清理範圍。", 409
                )
            targets = list(records) if all_items else list(dict.fromkeys(ids))
            if any(item_id not in records for item_id in targets):
                raise PipelineError("cleanup_missing", "部分項目已不存在，請重新整理後重試。", 404)
            if kind == "documents":
                busy = any(
                    self.active_documents[did]
                    or documents[did]["status"] not in {"ready", "failed", "delete_failed"}
                    for did in targets
                )
            else:
                busy = (all_items and self.active_queries > 0) or any(
                    records[rid] == "running" for rid in targets
                )
            if busy:
                raise PipelineError(
                    "cleanup_busy", "選取的資料正在處理或查詢，請等待完成後重試清理。", 409
                )
            result = {"kind": kind, "deleted_ids": [], "failures": []}
            if kind == "runs":
                self.store.delete_runs(targets)
                result["deleted_ids"] = targets
                return result
            # Check every path before touching vectors or files.
            for did in targets:
                folder = self.store.directory / "documents" / did
                try:
                    valid_id = str(uuid.UUID(did)) == did
                except ValueError:
                    valid_id = False
                if (
                    not valid_id
                    or folder.is_symlink()
                    or folder.resolve().parent != (self.store.directory / "documents").resolve()
                ):
                    raise PipelineError(
                        "cleanup_invalid_path", "文件儲存路徑異常，請檢查後端儲存目錄。", 409
                    )
            for did in targets:
                doc = documents[did]
                doc.update(status="deleting", error=None, updated_at=now())
                self.store.save_document(doc)
                try:
                    # Confirm vector removal before deleting the local source of truth.
                    self.index.delete_document(did)
                    folder = self.store.directory / "documents" / did
                    if folder.exists():
                        shutil.rmtree(folder)
                    self.store.delete_document(did)
                    result["deleted_ids"].append(did)
                except Exception as exc:
                    code = exc.code if isinstance(exc, PipelineError) else "cleanup_files_failed"
                    message = (
                        exc.message
                        if isinstance(exc, PipelineError)
                        else "無法移除本機文件，請檢查資料目錄權限與後端日誌後重試。"
                    )
                    doc.update(status="delete_failed", error=message, updated_at=now())
                    self.store.save_document(doc)
                    result["failures"].append({"id": did, "code": code, "message": message})
            return result
