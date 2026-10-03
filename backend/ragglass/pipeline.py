import json
import logging
import threading
import time
import uuid

from .embedding import Embedder
from .errors import PipelineError
from .llm import LLMClient, make_prompt, validate_completion
from .parser import Parser, make_chunks
from .retrieval import VectorIndex
from .store import now
from .workspace import Workspace

log = logging.getLogger(__name__)


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

    def _ingest(self, doc_id):
        with self.ingest_lock:
            doc = self.store.document(doc_id)
            if not doc:
                return
            started = time.perf_counter()
            timings = {}

            def stage(name, operation):
                doc.update(status=name, timings_ms=timings)
                self.store.save_document(doc)
                t = time.perf_counter()
                try:
                    return operation()
                finally:
                    timings[name] = round((time.perf_counter() - t) * 1000, 2)

            try:
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
                vectors = stage(
                    "embedding", lambda: self.embedder.encode([c["text"] for c in chunks])
                )
                stage("indexing", lambda: self.index.index(chunks, vectors))
                doc.update(
                    status="ready",
                    page_count=parsed["page_count"],
                    chunk_count=len(chunks),
                    collection=self.index.collection,
                    embedding=self.embedder.snapshot(),
                    parser=self.parser.snapshot(),
                    chunking=self.chunk_snapshot(),
                    error=None,
                )
            except Exception as exc:
                log.exception("Ingestion failed for document %s", doc_id)
                doc.update(
                    status="failed",
                    error=exc.message
                    if isinstance(exc, PipelineError)
                    else ("文件處理失敗。請檢查後端日誌與模型下載連線，修正後按重新索引。"),
                )
            finally:
                timings["total"] = round((time.perf_counter() - started) * 1000, 2)
                doc.update(timings_ms=timings, updated_at=now())
                self.store.save_document(doc)

    def query(self, question, documents, top_k, threshold):
        with self.workspace.activity([d["id"] for d in documents], query=True):
            current = [self.store.document(d["id"]) for d in documents]
            if any(d is None for d in current):
                raise PipelineError("cleanup_missing", "文件已刪除，請重新選取文件。", 404)
            if any(d["status"] != "ready" for d in current):
                raise PipelineError("cleanup_busy", "文件尚未完成索引，請等待或重新索引。", 409)
            return self._query(question, current, top_k, threshold)

    def _query(self, question, documents, top_k, threshold):
        started = time.perf_counter()
        run = {
            "id": str(uuid.uuid4()),
            "created_at": now(),
            "status": "running",
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

        def stage(name, operation):
            t = time.perf_counter()
            try:
                return operation()
            finally:
                run["timings_ms"][name] = round((time.perf_counter() - t) * 1000, 2)

        try:
            vector = stage("embedding", lambda: self.embedder.encode([question], query=True)[0])
            evidence = stage(
                "retrieval",
                lambda: self.index.search(vector, run["document_ids"], top_k, threshold),
            )
            run["evidence"] = evidence
            run["prompt"] = make_prompt(question, evidence)
            self.store.save_run(run)
            if evidence:
                raw, metrics = stage("generation", lambda: self.llm.generate(run["prompt"]))
                run.update(raw_response=raw, model_metrics=metrics)
                run.update(stage("citation_validation", lambda: validate_completion(raw, evidence)))
            else:
                run.update(answer="檢索未找到符合門檻的證據，無法從文件確認答案。")
            run["status"] = "completed"
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
            run["timings_ms"]["total"] = round((time.perf_counter() - started) * 1000, 2)
            run["finished_at"] = now()
            self.store.save_run(run)
        return run
