"""Synthetic lifecycle contracts; real Docling/E5/model evidence is checked separately."""

import asyncio
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from ragglass.config import Settings
from ragglass.errors import PipelineError
from ragglass.main import create_app
from ragglass.store import now


def stack(tmp_path, monkeypatch):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    pipeline = app.state.pipeline
    did = str(uuid.uuid4())
    doc = {
        "id": did,
        "hash": "synthetic-query-fixture",
        "filename": "fixture.pdf",
        "status": "ready",
        "parser": {},
        "chunking": {},
        "embedding": {},
        "collection": pipeline.index.collection,
    }
    app.state.store.save_document(doc)
    folder = tmp_path / "documents" / did
    folder.mkdir()
    (folder / "original.pdf").write_text("Synthetic query fixture; not a real PDF")
    evidence = [
        {
            "id": str(uuid.uuid4()),
            "document_id": did,
            "document_hash": doc["hash"],
            "filename": doc["filename"],
            "page": 2,
            "pages": [2],
            "text": "The maximum upload is 30 MB.",
            "provenance": [],
            "coordinates_available": False,
            "coordinate_scope": "unavailable",
            "score": 0.9,
            "rank": 1,
        }
    ]
    monkeypatch.setattr(pipeline.embedder, "encode", lambda *a, **kw: [[0.1, 0.2]])
    monkeypatch.setattr(pipeline.index, "search", lambda *a: evidence)
    request = {"question": "Maximum upload?", "document_ids": [did]}
    return app, evidence, request


def terminal(client, rid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{rid}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.01)
    raise AssertionError("Synthetic query did not finish")


def test_stop_generation_closes_await_retains_evidence_and_is_idempotent(tmp_path, monkeypatch):
    app, evidence, request = stack(tmp_path, monkeypatch)
    entered, closed = threading.Event(), threading.Event()

    async def slow_model(_):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            closed.set()

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", slow_model)
    with TestClient(app) as client:
        response = client.post("/api/query/start", json=request)
        assert response.status_code == 202
        rid = response.json()["id"]
        assert entered.wait(5)
        progress = client.get(f"/api/runs/{rid}").json()
        assert progress["stage"] == "generation"
        assert progress["evidence"][0]["id"] == evidence[0]["id"]
        assert progress["answer"] is None and not progress["citations"]
        assert client.post(f"/api/runs/{rid}/cancel").status_code == 200
        stopped = terminal(client, rid)
        assert closed.wait(1)
        assert stopped["status"] == stopped["stage"] == "cancelled"
        assert stopped["prompt"] and stopped["evidence"] and stopped["cancel_requested"]
        assert stopped["answer"] is None and not stopped["citations"]
        assert stopped["timings_ms"]["generation"] >= 0
        assert client.post(f"/api/runs/{rid}/cancel").json() == stopped
        assert client.get("/api/runs/catalog?status=cancelled").json()["matched"] == 1
        assert app.state.pipeline.workspace.active_queries == 0
        assert not app.state.query_jobs.active
        assert client.delete(f"/api/runs/{rid}").status_code == 200


def test_stop_cpu_waits_for_operation_and_keeps_cleanup_and_reindex_locked(tmp_path, monkeypatch):
    app, _, request = stack(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    retrieval_calls = []

    def slow_embedding(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return [[0.1, 0.2]]

    monkeypatch.setattr(app.state.pipeline.embedder, "encode", slow_embedding)
    monkeypatch.setattr(app.state.pipeline.index, "search", lambda *a: retrieval_calls.append(a))
    with TestClient(app) as client:
        try:
            rid = client.post("/api/query/start", json=request).json()["id"]
            assert entered.wait(5)
            pending = client.post(f"/api/runs/{rid}/cancel").json()
            assert pending["status"] == "running" and pending["cancel_requested"]
            did = request["document_ids"][0]
            assert client.delete(f"/api/documents/{did}").status_code == 409
            assert client.delete(f"/api/runs/{rid}").status_code == 409
            assert client.post(f"/api/documents/{did}/reindex").status_code == 409
        finally:
            release.set()
        assert terminal(client, rid)["status"] == "cancelled"
        assert not retrieval_calls
        assert app.state.pipeline.workspace.active_documents[did] == 0


@pytest.mark.parametrize("response_kind", ["valid", "invalid_citation", "unavailable"])
def test_async_completion_validates_citations_and_persists_failure(
    tmp_path, monkeypatch, response_kind
):
    app, evidence, request = stack(tmp_path, monkeypatch)

    async def model(_):
        if response_kind == "unavailable":
            raise PipelineError("llm_unavailable", "Synthetic endpoint failure")
        return (
            json.dumps(
                {
                    "answerable": True,
                    "answer": "30 MB",
                    "citation_ids": [
                        evidence[0]["id"] if response_kind == "valid" else str(uuid.uuid4())
                    ],
                }
            ),
            {"model": "synthetic-contract-model"},
        )

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post("/api/query/start", json=request).json()["id"]
        run = terminal(client, rid)
        assert run["evidence"] and run["prompt"] and run["finished_at"]
        if response_kind == "valid":
            assert run["status"] == "completed" and run["answer"] == "30 MB"
            assert run["citations"][0]["id"] == evidence[0]["id"]
            # Existing scripts and clients keep the synchronous API contract.
            assert client.post("/api/query", json=request).json()["answer"] == "30 MB"
        else:
            assert run["status"] == "failed" and run["answer"] is None
            assert not run["citations"]
            assert run["error_code"] == (
                "llm_unavailable" if response_kind == "unavailable" else "invalid_citation"
            )


def test_stop_retrieval_retains_finished_evidence_without_starting_model(tmp_path, monkeypatch):
    app, evidence, request = stack(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()

    def slow_retrieval(*args):
        entered.set()
        assert release.wait(5)
        return evidence

    async def unexpected_model(_):
        raise AssertionError("Generation must not start after cancellation")

    monkeypatch.setattr(app.state.pipeline.index, "search", slow_retrieval)
    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", unexpected_model)
    with TestClient(app) as client:
        try:
            rid = client.post("/api/query/start", json=request).json()["id"]
            assert entered.wait(5)
            client.post(f"/api/runs/{rid}/cancel").raise_for_status()
        finally:
            release.set()
        stopped = terminal(client, rid)
        assert stopped["status"] == "cancelled"
        assert stopped["evidence"][0]["id"] == evidence[0]["id"] and stopped["prompt"]
        assert "generation" not in stopped["timings_ms"]


def test_shutdown_stops_active_generation_and_restart_keeps_cancelled_record(tmp_path, monkeypatch):
    app, _, request = stack(tmp_path, monkeypatch)
    entered = threading.Event()

    async def model(_):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post("/api/query/start", json=request).json()["id"]
        assert entered.wait(5)
    stored = app.state.store.run(rid)
    assert stored["status"] == "cancelled" and stored["evidence"]
    app.state.store.recover_interrupted()
    assert app.state.store.run(rid) == stored
    assert app.state.pipeline.workspace.active_queries == 0
    assert now() >= stored["finished_at"]


def test_stop_closes_actual_model_http_connection(tmp_path, monkeypatch):
    # Real loopback HTTP transport with a deliberately waiting synthetic model server.
    # This proves request disconnection, not model quality or GPU compute cancellation.
    entered, disconnected = threading.Event(), threading.Event()

    class WaitingModel(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            entered.set()
            self.connection.settimeout(5)
            if self.connection.recv(1) == b"":
                disconnected.set()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), WaitingModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    app, _, request = stack(tmp_path, monkeypatch)
    app.state.pipeline.settings.llm_base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with TestClient(app) as client:
            rid = client.post("/api/query/start", json=request).json()["id"]
            assert entered.wait(5)
            client.post(f"/api/runs/{rid}/cancel").raise_for_status()
            assert terminal(client, rid)["status"] == "cancelled"
            assert disconnected.wait(2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
