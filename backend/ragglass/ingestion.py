"""Single-worker document queue with cooperative cancellation and persisted progress."""

import asyncio
import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .errors import PipelineError
from .store import now

DOCUMENT_TERMINAL = {"ready", "failed", "cancelled", "delete_failed"}


class IngestCancelled(Exception):
    pass


class IngestControl:
    def __init__(self, store, doc):
        self.store = store
        self.doc = copy.deepcopy(doc)
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.queued_at = time.perf_counter()

    def update(self, **values):
        with self.lock:
            self.doc.update(values, updated_at=now())
            self.store.save_document(self.doc)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.doc)

    def request_cancel(self):
        with self.lock:
            if self.doc["status"] not in DOCUMENT_TERMINAL and not self.cancelled.is_set():
                self.cancelled.set()
                self.update(cancel_requested=True, cancel_requested_at=now())
            return self.snapshot()

    def check(self):
        if self.cancelled.is_set():
            raise IngestCancelled


class IngestJobs:
    """All queue membership changes hold the workspace lock; CPU work never holds it."""

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ragglass-ingest")
        self.active = {}
        self.closing = False

    def enqueue(self, doc):
        # The upload/reindex route holds workspace.mutation() through registration.
        if self.closing:
            raise PipelineError("ingestion_closing", "服務正在關閉，請稍後重試。", 503)
        did = doc["id"]
        if did in self.active:
            raise PipelineError("cleanup_busy", "文件正在處理，請等待完成。", 409)
        doc.update(
            status="queued",
            queued_at=now(),
            processing_started_at=None,
            stage_started_at=None,
            finished_at=None,
            cancel_requested=False,
            cancel_requested_at=None,
            error=None,
            error_code=None,
            chunk_count=0,
            timings_ms={},
            progress={"total_chunks": None, "embedded_chunks": 0, "indexed_chunks": 0},
            ingestion={"vector_batch_size": self.pipeline.settings.ingest_batch_size},
            parser=self.pipeline.parser.snapshot(),
            chunking=self.pipeline.chunk_snapshot(),
            embedding=self.pipeline.embedder.snapshot(),
            target_collection=self.pipeline.index.collection,
            partial_index_collection=None,
        )
        control = IngestControl(self.pipeline.store, doc)
        control.update()
        self.pipeline.workspace.active_documents[did] += 1
        self.active[did] = (control, None)
        try:
            future = self.executor.submit(self._execute, did, control)
            self.active[did] = (control, future)
        except BaseException:
            self._release(did)
            control.update(status="failed", error="無法排入處理佇列，請重新索引。")
            raise
        return doc

    def _release(self, did):
        # Caller holds the workspace lock.
        self.active.pop(did, None)
        self.pipeline.workspace.active_documents[did] -= 1

    def _execute(self, did, control):
        try:
            self.pipeline._ingest(did, control)
        finally:
            with self.pipeline.workspace.lock:
                self._release(did)

    def _cancel(self, did):
        current = self.active.get(did)
        if current:
            control, future = current
            control.request_cancel()
            if future.cancel():
                control.update(
                    status="cancelled",
                    finished_at=now(),
                    timings_ms={
                        "queue_wait": round((time.perf_counter() - control.queued_at) * 1000, 2),
                        "total": 0,
                    },
                )
                self._release(did)
            return control.snapshot()
        doc = self.pipeline.store.document(did)
        if doc is None:
            raise PipelineError("document_missing", "找不到文件，請重新整理文件列表。", 404)
        if doc["status"] not in DOCUMENT_TERMINAL:
            raise PipelineError("ingestion_not_cancellable", "此文件沒有可停止的作業。", 409)
        return doc

    def cancel(self, did):
        with self.pipeline.workspace.mutation():
            return self._cancel(did)

    async def close(self):
        with self.pipeline.workspace.lock:
            self.closing = True
            for did in list(self.active):
                self._cancel(did)
        # Wait for the current CPU operation; do not terminate shared model services.
        await asyncio.to_thread(self.executor.shutdown, wait=True)
