import hashlib
import uuid
from contextlib import asynccontextmanager
from io import BytesIO

import httpx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from pypdf import PdfReader

from .config import ROOT, Settings
from .errors import PipelineError
from .pipeline import Pipeline
from .store import Store, now


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] = Field(min_length=1, max_length=30)
    top_k: int = Field(default=5, ge=1, le=12)
    score_threshold: float = Field(default=0.70, ge=0, le=1)


class CleanupSelection(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=500)
    all: bool = False
    expected_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def explicit_scope(self):
        if self.all == bool(self.ids):
            raise ValueError("Choose non-empty ids or all, exclusively.")
        if self.all and self.expected_count is None:
            raise ValueError("all requires the confirmed expected_count.")
        return self


def create_app(settings=None):
    s = settings or Settings()
    s.configure_paths()
    store = Store(s.ragglass_data_dir)
    pipeline = Pipeline(s, store)

    @asynccontextmanager
    async def lifespan(app):
        store.recover_interrupted()
        yield
        pipeline.index.client.close()

    app = FastAPI(title="RAGGlass", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.pipeline = pipeline

    @app.exception_handler(PipelineError)
    async def pipeline_error(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    def get_doc(doc_id):
        doc = store.document(doc_id)
        if not doc:
            raise HTTPException(404, "找不到文件，請重新整理文件列表。")
        return doc

    def source_ids():
        return {
            d["id"]
            for d in store.documents()
            if (store.directory / "documents" / d["id"] / "original.pdf").is_file()
        }

    def source_status(record, available):
        # Availability is current metadata, not a rewrite of the historical evidence.
        return {
            **record,
            "missing_document_ids": [did for did in record["document_ids"] if did not in available],
            **{
                key: [
                    {**item, "source_available": item["document_id"] in available}
                    for item in record[key]
                ]
                for key in ("evidence", "citations")
            },
        }

    @app.get("/api/health")
    def health():
        dependencies = {}
        with httpx.Client(timeout=3, trust_env=False) as client:
            for name, url, key in (
                ("qdrant", s.qdrant_url.rstrip("/") + "/readyz", s.qdrant_api_key),
                (
                    "llm",
                    s.llm_base_url.rstrip("/")
                    + ("/api/tags" if s.llm_provider == "ollama" else "/models"),
                    s.llm_api_key,
                ),
            ):
                try:
                    headers = (
                        {"api-key": key}
                        if name == "qdrant" and key
                        else ({"Authorization": f"Bearer {key}"} if key else {})
                    )
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    if name == "llm":
                        data = response.json()
                        names = [
                            m.get("name", m.get("id"))
                            for m in data.get(
                                "models" if s.llm_provider == "ollama" else "data", []
                            )
                        ]
                        dependencies[name] = "ready" if s.llm_model in names else "model_missing"
                    else:
                        dependencies[name] = "ready"
                except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                    dependencies[name] = "unavailable"
        return {"status": "ok", "dependencies": dependencies}

    @app.get("/api/config")
    def config():
        return {
            "llm": pipeline.llm.snapshot(),
            "embedding": pipeline.embedder.snapshot(),
            "parser": pipeline.parser.snapshot(),
            "chunking": pipeline.chunk_snapshot(),
            "retrieval": {
                "top_k": s.retrieval_top_k,
                "score_threshold": s.retrieval_score_threshold,
            },
            "max_upload_mb": s.max_upload_mb,
        }

    @app.get("/api/documents")
    def documents():
        return store.documents()

    @app.post("/api/documents/cleanup")
    def cleanup_documents(request: CleanupSelection):
        return pipeline.workspace.cleanup(
            "documents", request.ids, request.all, request.expected_count
        )

    @app.delete("/api/documents/{doc_id}")
    def delete_document(doc_id: str):
        return pipeline.workspace.cleanup("documents", [doc_id])

    @app.post("/api/documents", status_code=202)
    async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
        data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
        await file.close()
        if len(data) > s.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"PDF 超過 {s.max_upload_mb} MB，請縮小或拆分檔案。")
        if not data.startswith(b"%PDF-"):
            raise HTTPException(422, "檔案不是有效的 PDF，請上傳 PDF 文件。")
        try:
            pdf = PdfReader(BytesIO(data))
            if pdf.is_encrypted:
                raise HTTPException(422, "PDF 已加密，請先移除密碼後上傳。")
            page_count = len(pdf.pages)
            if not 1 <= page_count <= s.max_pdf_pages:
                raise HTTPException(422, f"PDF 頁數須介於 1 與 {s.max_pdf_pages}，請拆分文件。")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, "PDF 損壞或無法讀取，請重新匯出 PDF。") from exc
        digest = hashlib.sha256(data).hexdigest()
        with pipeline.workspace.mutation():
            existing = store.by_hash(digest)
            if existing:
                return {**existing, "duplicate": True}
            doc_id = str(uuid.uuid4())
            folder = store.directory / "documents" / doc_id
            folder.mkdir()
            (folder / "original.pdf").write_bytes(data)
            filename = (file.filename or "document.pdf").replace("\\", "/").split("/")[-1][:200]
            doc = {
                "id": doc_id,
                "hash": digest,
                "filename": filename,
                "status": "queued",
                "created_at": now(),
                "updated_at": now(),
                "page_count": page_count,
                "chunk_count": 0,
                "error": None,
                "parser": pipeline.parser.snapshot(),
                "chunking": pipeline.chunk_snapshot(),
                "embedding": pipeline.embedder.snapshot(),
                "timings_ms": {},
            }
            store.save_document(doc)
            background_tasks.add_task(pipeline.ingest, doc_id)
            return doc

    @app.get("/api/documents/{doc_id}")
    def document(doc_id: str):
        return get_doc(doc_id)

    @app.get("/api/documents/{doc_id}/pdf")
    def pdf(doc_id: str):
        get_doc(doc_id)
        if not (store.directory / "documents" / doc_id / "original.pdf").is_file():
            raise HTTPException(404, "原始 PDF 已不存在，請完成清理後重新上傳。")
        return FileResponse(
            store.directory / "documents" / doc_id / "original.pdf", media_type="application/pdf"
        )

    @app.get("/api/documents/{doc_id}/chunks")
    def chunks(doc_id: str):
        get_doc(doc_id)
        return store.chunks(doc_id)

    @app.get("/api/documents/{doc_id}/parsed")
    def parsed(doc_id: str, format: str = "markdown"):
        get_doc(doc_id)
        if format not in {"markdown", "json"}:
            raise HTTPException(422, "format must be markdown or json")
        path = (
            store.directory
            / "documents"
            / doc_id
            / ("parsed.md" if format == "markdown" else "docling.json")
        )
        if not path.exists():
            raise HTTPException(409, "解析尚未完成，請等待或查看文件錯誤。")
        return FileResponse(
            path, media_type="text/plain" if format == "markdown" else "application/json"
        )

    @app.post("/api/documents/{doc_id}/reindex", status_code=202)
    def reindex(doc_id: str, background_tasks: BackgroundTasks):
        with pipeline.workspace.mutation():
            doc = get_doc(doc_id)
            if doc["status"] not in {"ready", "failed", "delete_failed"}:
                raise HTTPException(409, "文件正在處理，請等待完成。")
            doc.update(status="queued", error=None, updated_at=now())
            store.save_document(doc)
            background_tasks.add_task(pipeline.ingest, doc_id)
            return doc

    @app.post("/api/query")
    def query(request: Query):
        question = request.question.strip()
        if not question:
            raise HTTPException(422, "請輸入問題。")
        docs = [get_doc(did) for did in dict.fromkeys(request.document_ids)]
        if any(d["status"] != "ready" for d in docs):
            raise HTTPException(409, "文件尚未完成索引，請等待或重新索引。")
        if any(d.get("collection") != pipeline.index.collection for d in docs):
            raise HTTPException(409, "Embedding 設定已更改，請重新索引文件後查詢。")
        # A failed generation still returns the saved run, including retrieval and actionable error.
        return source_status(
            pipeline.query(question, docs, request.top_k, request.score_threshold), source_ids()
        )

    @app.get("/api/runs")
    def runs(limit: int = 100, offset: int = 0):
        available = source_ids()
        return [
            source_status(r, available) for r in store.runs(min(max(limit, 1), 500), max(offset, 0))
        ]

    @app.get("/api/runs/catalog")
    def run_catalog(search: str = "", status: str = "", offset: int = 0, limit: int = 50):
        if len(search) > 200 or status not in {"", "completed", "failed", "running"}:
            raise HTTPException(422, "Invalid history search or status.")
        result = store.run_catalog(search, status, max(offset, 0), min(max(limit, 1), 100))
        available = source_ids()
        result["items"] = [source_status(r, available) for r in result["items"]]
        return result

    @app.post("/api/runs/cleanup")
    def cleanup_runs(request: CleanupSelection):
        return pipeline.workspace.cleanup("runs", request.ids, request.all, request.expected_count)

    @app.delete("/api/runs/{run_id}")
    def delete_run(run_id: str):
        return pipeline.workspace.cleanup("runs", [run_id])

    @app.get("/api/runs/{run_id}")
    def run(run_id: str):
        result = store.run(run_id)
        if not result:
            raise HTTPException(404, "找不到執行紀錄。")
        return source_status(result, source_ids())

    @app.get("/api/sample.pdf")
    def sample():
        return FileResponse(
            ROOT / "examples" / "ragglass-field-guide.pdf", media_type="application/pdf"
        )

    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
