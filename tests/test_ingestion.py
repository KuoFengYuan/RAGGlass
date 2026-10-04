"""Synthetic lifecycle/batch contracts; no Docling or model inference in these tests."""

import gc
import threading
import time
import uuid
import weakref
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from ragglass.config import Settings
from ragglass.errors import PipelineError
from ragglass.main import create_app
from ragglass.store import Store, now


def stack(tmp_path, monkeypatch, count=11):
    app = create_app(Settings(ragglass_data_dir=tmp_path, ingest_batch_size=4))
    pipeline = app.state.pipeline
    pipeline.embedder._model = SimpleNamespace(tokenizer=None)
    monkeypatch.setattr(
        pipeline.parser,
        "parse",
        lambda _: {"groups": [], "page_count": 1, "docling": {}, "markdown": "Synthetic text"},
    )

    def chunks(_, doc, *args):
        return [
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc['id']}:{i}")),
                "document_id": doc["id"],
                "document_hash": doc["hash"],
                "text": f"Synthetic chunk {i}",
                "pages": [1],
            }
            for i in range(count)
        ]

    monkeypatch.setattr("ragglass.pipeline.make_chunks", chunks)
    monkeypatch.setattr(pipeline.embedder, "encode", lambda texts: [[0.1, 0.2] for _ in texts])
    monkeypatch.setattr(pipeline.index, "begin_document", lambda *args: None)
    monkeypatch.setattr(pipeline.index, "upsert_batch", lambda *args: None)
    return app


def seed(app):
    did = str(uuid.uuid4())
    doc = {
        "id": did,
        "hash": did,
        "filename": "synthetic.pdf",
        "status": "ready",
        "page_count": 1,
        "chunk_count": 0,
        "created_at": now(),
    }
    app.state.store.save_document(doc)
    folder = app.state.store.directory / "documents" / did
    folder.mkdir()
    (folder / "original.pdf").write_text("Synthetic lifecycle fixture, not a PDF")
    return did


def terminal(client, app, did):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        doc = client.get(f"/api/documents/{did}").json()
        if (
            doc["status"] in {"ready", "failed", "cancelled"}
            and not (app.state.pipeline.workspace.active_documents[did])
        ):
            return doc
        time.sleep(0.005)
    raise AssertionError("Synthetic ingestion did not finish")


def test_batches_are_released_before_next_encode_and_index_is_prepared_once(tmp_path, monkeypatch):
    app = stack(tmp_path, monkeypatch)
    pipeline = app.state.pipeline
    operations, references = [], []

    class Vectors(list):
        pass

    def encode(texts):
        gc.collect()
        assert not references or references[-1]() is None
        operations.append(("encode", len(texts)))
        vectors = Vectors([[0.1, 0.2] for _ in texts])
        references.append(weakref.ref(vectors))
        return vectors

    monkeypatch.setattr(pipeline.embedder, "encode", encode)
    monkeypatch.setattr(pipeline.index, "begin_document", lambda *args: operations.append("begin"))
    monkeypatch.setattr(
        pipeline.index, "upsert_batch", lambda c, v: operations.append(("write", len(v)))
    )
    with TestClient(app) as client:
        did = seed(app)
        assert client.post(f"/api/documents/{did}/reindex").status_code == 202
        doc = terminal(client, app, did)
        assert doc["status"] == "ready"
        assert operations == [
            ("encode", 4),
            "begin",
            ("write", 4),
            ("encode", 4),
            ("write", 4),
            ("encode", 3),
            ("write", 3),
        ]
        assert doc["progress"] == {
            "total_chunks": 11,
            "embedded_chunks": 11,
            "indexed_chunks": 11,
        }
        assert doc["ingestion"]["vector_batch_size"] == 4
        assert all(
            doc["timings_ms"][stage] >= 0
            for stage in ("queue_wait", "parsing", "chunking", "embedding", "indexing", "total")
        )
        assert doc["processing_started_at"] and doc["finished_at"]


def test_stop_parser_keeps_source_and_blocks_mutations_until_cpu_returns(tmp_path, monkeypatch):
    app = stack(tmp_path, monkeypatch)
    pipeline = app.state.pipeline
    entered, release = threading.Event(), threading.Event()
    original = pipeline.parser.parse
    encoding = []

    def parse(path):
        entered.set()
        assert release.wait(5)
        return original(path)

    monkeypatch.setattr(pipeline.parser, "parse", parse)
    monkeypatch.setattr(pipeline.embedder, "encode", lambda *args: encoding.append(args))
    with TestClient(app) as client:
        did = seed(app)
        try:
            client.post(f"/api/documents/{did}/reindex").raise_for_status()
            assert entered.wait(5)
            stopped = client.post(f"/api/documents/{did}/cancel").json()
            assert stopped["status"] == "parsing" and stopped["cancel_requested"]
            assert client.delete(f"/api/documents/{did}").status_code == 409
            assert client.post(f"/api/documents/{did}/reindex").status_code == 409
            assert (
                client.post(
                    "/api/query/start",
                    json={
                        "question": "Any fact?",
                        "document_ids": [did],
                    },
                ).status_code
                == 409
            )
        finally:
            release.set()
        doc = terminal(client, app, did)
        assert doc["status"] == "cancelled" and not encoding
        assert client.post(f"/api/documents/{did}/cancel").json() == doc
        folder = tmp_path / "documents" / did
        assert (folder / "original.pdf").exists() and (folder / "parsed.md").exists()
        Store(tmp_path).recover_interrupted()
        assert app.state.store.document(did) == doc
        monkeypatch.setattr(pipeline.index, "delete_document", lambda _: None)
        assert client.delete(f"/api/documents/{did}").status_code == 200


def test_cancel_queued_document_releases_it_without_parsing(tmp_path, monkeypatch):
    app = stack(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    paths = []
    original = app.state.pipeline.parser.parse

    def parse(path):
        paths.append(path.parent.name)
        entered.set()
        assert release.wait(5)
        return original(path)

    monkeypatch.setattr(app.state.pipeline.parser, "parse", parse)
    with TestClient(app) as client:
        first, queued = seed(app), seed(app)
        try:
            client.post(f"/api/documents/{first}/reindex").raise_for_status()
            assert entered.wait(5)
            response = client.post(f"/api/documents/{queued}/reindex")
            assert response.json()["status"] == "queued"
            assert client.delete(f"/api/documents/{queued}").status_code == 409
            stopped = client.post(f"/api/documents/{queued}/cancel").json()
            assert stopped["status"] == "cancelled" and stopped["cancel_requested"]
            assert app.state.pipeline.workspace.active_documents[queued] == 0
        finally:
            release.set()
        assert terminal(client, app, first)["status"] == "ready"
        assert paths == [first]
        assert client.post(f"/api/documents/{queued}/reindex").status_code == 202
        assert terminal(client, app, queued)["status"] == "ready"


@pytest.mark.parametrize("stop_at", ["embedding", "indexing"])
def test_stop_batch_preserves_confirmed_counts_and_starts_no_next_batch(
    tmp_path, monkeypatch, stop_at
):
    app = stack(tmp_path, monkeypatch)
    pipeline = app.state.pipeline
    entered, release = threading.Event(), threading.Event()
    encoded, written = [], []

    def encode(texts):
        encoded.append(len(texts))
        if len(encoded) == 2 and stop_at == "embedding":
            entered.set()
            assert release.wait(5)
        return [[0.1, 0.2] for _ in texts]

    def write(chunks, vectors):
        written.append(len(chunks))
        if len(written) == 2 and stop_at == "indexing":
            entered.set()
            assert release.wait(5)

    monkeypatch.setattr(pipeline.embedder, "encode", encode)
    monkeypatch.setattr(pipeline.index, "upsert_batch", write)
    with TestClient(app) as client:
        did = seed(app)
        try:
            client.post(f"/api/documents/{did}/reindex").raise_for_status()
            assert entered.wait(5)
            progress = client.get(f"/api/documents/{did}").json()
            assert progress["progress"]["indexed_chunks"] == 4
            assert client.post(f"/api/documents/{did}/cancel").status_code == 200
        finally:
            release.set()
        doc = terminal(client, app, did)
        assert doc["status"] == "cancelled" and encoded == [4, 4]
        assert written == ([4] if stop_at == "embedding" else [4, 4])
        assert doc["progress"]["embedded_chunks"] == 8
        assert doc["progress"]["indexed_chunks"] == (4 if stop_at == "embedding" else 8)
        assert len(app.state.store.chunks(did)) == 11


def test_write_failure_retains_progress_and_reindex_resets_all_counts(tmp_path, monkeypatch):
    app = stack(tmp_path, monkeypatch)
    pipeline = app.state.pipeline
    calls = []

    def write(chunks, vectors):
        calls.append(chunks)
        if len(calls) == 2:
            raise PipelineError("qdrant_unavailable", "Synthetic failed write")

    monkeypatch.setattr(pipeline.index, "upsert_batch", write)
    with TestClient(app) as client:
        did = seed(app)
        client.post(f"/api/documents/{did}/reindex").raise_for_status()
        failed = terminal(client, app, did)
        assert failed["status"] == "failed" and failed["error_code"] == "qdrant_unavailable"
        assert failed["progress"] == {
            "total_chunks": 11,
            "embedded_chunks": 8,
            "indexed_chunks": 4,
        }
        monkeypatch.setattr(pipeline.index, "upsert_batch", lambda *args: None)
        client.post(f"/api/documents/{did}/reindex").raise_for_status()
        restored = terminal(client, app, did)
        assert restored["status"] == "ready" and not restored["cancel_requested"]
        assert restored["progress"]["indexed_chunks"] == 11 and not restored["error"]


def test_stop_during_last_write_does_not_publish_ready_document(tmp_path, monkeypatch):
    app = stack(tmp_path, monkeypatch, count=4)
    did = seed(app)
    monkeypatch.setattr(
        app.state.pipeline.index, "upsert_batch", lambda *args: app.state.ingest_jobs.cancel(did)
    )
    with TestClient(app) as client:
        client.post(f"/api/documents/{did}/reindex").raise_for_status()
        doc = terminal(client, app, did)
        assert doc["progress"]["indexed_chunks"] == doc["progress"]["total_chunks"] == 4
        assert doc["status"] == "cancelled" and doc["cancel_requested"]
        assert (
            client.post(
                "/api/query/start", json={"question": "A fact?", "document_ids": [did]}
            ).status_code
            == 409
        )


def test_vector_batches_keep_previous_points_and_reindex_removes_obsolete_ids(tmp_path):
    # Real in-memory Qdrant client, synthetic vectors; not a live Qdrant/model check.
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    index = app.state.pipeline.index
    index.client.close()
    index.client = QdrantClient(":memory:")
    did = str(uuid.uuid4())
    chunks = [{"id": str(uuid.uuid4()), "document_id": did} for _ in range(5)]
    other = {"id": str(uuid.uuid4()), "document_id": str(uuid.uuid4())}
    with TestClient(app):
        index.begin_document(other["document_id"], 2)
        index.upsert_batch([other], [[0.2, 0.3]])
        index.begin_document(did, 2)
        index.upsert_batch(chunks[:2], [[0.1, 0.2]] * 2)
        index.upsert_batch(chunks[2:], [[0.1, 0.2]] * 3)
        assert index.client.count(index.collection, exact=True).count == 6
        index.begin_document(did, 2)
        index.upsert_batch(chunks[:1], [[0.1, 0.2]])
        assert index.client.count(index.collection, exact=True).count == 2
        assert len(index.search([0.1, 0.2], [did], 12, 0)) == 1


def test_shutdown_requests_stop_and_waits_for_current_cpu_operation(tmp_path, monkeypatch):
    app = stack(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    original = app.state.pipeline.parser.parse

    def parse(path):
        entered.set()
        assert release.wait(5)
        return original(path)

    monkeypatch.setattr(app.state.pipeline.parser, "parse", parse)
    client = TestClient(app)
    client.__enter__()
    did = seed(app)
    client.post(f"/api/documents/{did}/reindex").raise_for_status()
    assert entered.wait(5)
    closer = threading.Thread(target=lambda: client.__exit__(None, None, None))
    closer.start()
    try:
        deadline = time.monotonic() + 3
        while not app.state.store.document(did)["cancel_requested"]:
            assert time.monotonic() < deadline
            time.sleep(0.005)
        assert closer.is_alive() and app.state.pipeline.workspace.active_documents[did]
    finally:
        release.set()
        closer.join(5)
    assert not closer.is_alive() and not app.state.ingest_jobs.active
    assert app.state.store.document(did)["status"] == "cancelled"
