import asyncio
import json
import logging
import threading
import time
import uuid

from .embedding import Embedder
from .errors import PipelineError
from .ingestion import IngestCancelled, IngestControl
from .llm import LLMClient, make_prompt, validate_completion
from .parser import Parser, make_chunks
from .retrieval import VectorIndex
from .store import now
from .workspace import Workspace

log = logging.getLogger(__name__)


class QueryCancelled(Exception):
    """A cooperative stop, recorded separately from a failure."""


class QueryControl:
    def __init__(self):
        self.cancelled = False
        self.generation = None

    def cancel(self):
        self.cancelled = True
        if self.generation is not None:
            self.generation.cancel()

    def check(self):
        if self.cancelled:
            raise QueryCancelled


class Pipeline:
    def __init__(self, settings, store):
        self.settings = settings
        self.store = store
        self.embedder = Embedder(settings)
        self.parser = Parser(settings)
        self.index = VectorIndex(settings, self.embedder)
        self.llm = LLMClient(settings)
        self.ingest_lock = threading.Lock()
        self.workspace = Workspace(store, self.index)

    def chunk_snapshot(self):
        return {
            "strategy": "page-aware-token-window-v1",
            "tokens": self.settings.chunk_tokens,
            "overlap_tokens": self.settings.chunk_overlap_tokens,
            "tokenizer_model": self.settings.embedding_model,
            "tokenizer_revision": self.settings.embedding_revision,
            "multi_page_items": "retain_all_source_pages",
        }

    def ingest(self, doc_id):
        with self.workspace.activity([doc_id]):
            self._ingest(doc_id)

    def _ingest(self, doc_id, control=None):
        with self.ingest_lock:
            doc = self.store.document(doc_id)
            if not doc:
                return
            control = control or IngestControl(self.store, doc)
            started = time.perf_counter()
            timings = {"queue_wait": round((started - control.queued_at) * 1000, 2)}
            progress = {"total_chunks": None, "embedded_chunks": 0, "indexed_chunks": 0}

            def stage(name, operation):
                control.check()
                control.update(status=name, stage_started_at=now(), timings_ms=timings.copy())
                t = time.perf_counter()
                try:
                    return operation()
                finally:
                    timings[name] = round(
                        timings.get(name, 0) + (time.perf_counter() - t) * 1000, 2
                    )
                    control.update(timings_ms=timings.copy())

            try:
                control.check()
                control.update(processing_started_at=now(), progress=progress.copy())
                folder = self.store.directory / "documents" / doc_id
                parsed = stage("parsing", lambda: self.parser.parse(folder / "original.pdf"))
                (folder / "docling.json").write_text(
                    json.dumps(parsed["docling"], ensure_ascii=False), encoding="utf-8"
                )
                (folder / "parsed.md").write_text(parsed["markdown"], encoding="utf-8")
                chunks = stage(
                    "chunking",
                    lambda: make_chunks(
                        parsed,
                        doc,
                        self.embedder.model.tokenizer,
                        self.settings.chunk_tokens,
                        self.settings.chunk_overlap_tokens,
                    ),
                )
                if not chunks:
                    raise PipelineError(
                        "no_native_text", "PDF 未產生可引用片段，請檢查原生文字。", 422
                    )
                self.store.save_chunks(doc_id, chunks)
                progress["total_chunks"] = len(chunks)
                control.update(
                    chunk_count=len(chunks),
                    page_count=parsed["page_count"],
                    progress=progress.copy(),
                    parser=self.parser.snapshot(),
                    chunking=self.chunk_snapshot(),
                    embedding=self.embedder.snapshot(),
                )
                size = self.settings.ingest_batch_size
                for offset in range(0, len(chunks), size):
                    batch = chunks[offset : offset + size]
                    vectors = stage(
                        "embedding", lambda: self.embedder.encode([c["text"] for c in batch])
                    )
                    progress["embedded_chunks"] += len(batch)
                    control.update(progress=progress.copy())

                    def write_batch():
                        if offset == 0:
                            self.index.begin_document(doc_id, len(vectors[0]))
                            control.update(partial_index_collection=self.index.collection)
                        # A stop during preparation does not start another write.
                        control.check()
                        self.index.upsert_batch(batch, vectors)

                    stage("indexing", write_batch)
                    progress["indexed_chunks"] += len(batch)
                    control.update(progress=progress.copy())
                    # Release this batch before encoding the next one, including on stop.
                    vectors = None
                with control.lock:
                    control.check()
                    control.update(status="ready", collection=self.index.collection, error=None)
            except IngestCancelled:
                control.update(status="cancelled", error=None, error_code=None)
            except Exception as exc:
                log.exception("Ingestion failed for document %s", doc_id)
                control.update(
                    status="failed",
                    error_code=exc.code if isinstance(exc, PipelineError) else "ingestion_failed",
                    error=exc.message
                    if isinstance(exc, PipelineError)
                    else ("文件處理失敗。請檢查後端日誌與模型下載連線，修正後按重新索引。"),
                )
            finally:
                timings["total"] = round((time.perf_counter() - started) * 1000, 2)
                control.update(timings_ms=timings, finished_at=now())

    def query(self, question, documents, top_k, threshold):
        with self.workspace.activity([d["id"] for d in documents], query=True):
            run = self.new_query(question, documents, top_k, threshold)
            return asyncio.run(self.execute_query(run, QueryControl()))

    def new_query(self, question, documents, top_k, threshold):
        documents = [self.store.document(d["id"]) for d in documents]
        if any(d is None for d in documents):
            raise PipelineError("cleanup_missing", "文件已刪除，請重新選取文件。", 404)
        if any(d["status"] != "ready" for d in documents):
            raise PipelineError("cleanup_busy", "文件尚未完成索引，請等待或重新索引。", 409)
        if any(d.get("collection") != self.index.collection for d in documents):
            raise PipelineError("embedding_changed", "Embedding 設定已更改，請重新索引。", 409)
        run = {
            "id": str(uuid.uuid4()),
            "created_at": now(),
            "status": "running",
            "stage": "queued",
            "stage_started_at": now(),
            "cancel_requested": False,
            "question": question,
            "document_ids": [d["id"] for d in documents],
            "documents": [
                {
                    k: d[k]
                    for k in (
                        "id",
                        "hash",
                        "filename",
                        "parser",
                        "chunking",
                        "embedding",
                        "collection",
                    )
                }
                for d in documents
            ],
            "settings": {
                "llm": self.llm.snapshot(),
                "embedding": self.embedder.snapshot(),
                "retrieval": {
                    "strategy": "dense-cosine",
                    "top_k": top_k,
                    "score_threshold": threshold,
                    "collection": self.index.collection,
                },
                "prompt_version": "grounded-json-v1",
            },
            "timings_ms": {},
            "evidence": [],
            "citations": [],
            "answer": None,
            "answerable": False,
            "error": None,
            "error_code": None,
        }
        self.store.save_run(run)
        return run

    async def execute_query(self, run, control):
        started = time.perf_counter()
        retrieval = run["settings"]["retrieval"]

        async def stage(name, operation, threaded=True):
            control.check()
            run.update(stage=name, stage_started_at=now())
            self.store.save_run(run)
            t = time.perf_counter()
            try:
                if threaded:
                    # A running CPU/vector operation cannot be killed safely. Keep its activity
                    # reservation until it returns, then honour cancellation before another stage.
                    work = asyncio.create_task(asyncio.to_thread(operation))
                    try:
                        result = await asyncio.shield(work)
                    except asyncio.CancelledError:
                        await work
                        raise
                else:
                    control.generation = asyncio.create_task(operation())
                    try:
                        result = await control.generation
                    except asyncio.CancelledError:
                        control.check()
                        raise
                    finally:
                        control.generation = None
                return result
            finally:
                run["timings_ms"][name] = round((time.perf_counter() - t) * 1000, 2)
                self.store.save_run(run)

        try:
            vector = await stage(
                "embedding", lambda: self.embedder.encode([run["question"]], query=True)[0]
            )
            evidence = await stage(
                "retrieval",
                lambda: self.index.search(
                    vector, run["document_ids"], retrieval["top_k"], retrieval["score_threshold"]
                ),
            )
            run["evidence"] = evidence
            run["prompt"] = make_prompt(run["question"], evidence)
            self.store.save_run(run)
            if evidence:
                raw, metrics = await stage(
                    "generation", lambda: self.llm.generate_async(run["prompt"]), threaded=False
                )
                run.update(raw_response=raw, model_metrics=metrics)
                run.update(
                    await stage("citation_validation", lambda: validate_completion(raw, evidence))
                )
            else:
                run.update(answer="檢索未找到符合門檻的證據，無法從文件確認答案。")
            control.check()
            run["status"] = "completed"
        except QueryCancelled:
            run.update(status="cancelled", answer=None, answerable=False, citations=[])
        except asyncio.CancelledError:
            run.update(
                status="failed",
                error="查詢被服務關閉中斷，請重新送出問題。",
                error_code="interrupted",
            )
            raise
        except Exception as exc:
            log.exception("Query failed for run %s", run["id"])
            error = (
                exc
                if isinstance(exc, PipelineError)
                else PipelineError(
                    "query_failed", "查詢失敗。請檢查後端日誌與 embedding 模型下載，然後重試。", 500
                )
            )
            run.update(status="failed", error=error.message, error_code=error.code)
        finally:
            run["stage"] = run["status"]
            run["timings_ms"]["total"] = round((time.perf_counter() - started) * 1000, 2)
            run["finished_at"] = now()
            self.store.save_run(run)
        return run
