"""Synthetic storage/API contracts; live parser/model cleanup is checked separately."""

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
from ragglass.config import Settings
from ragglass.main import create_app
from ragglass.store import Store, now


def seed_document(store, status="ready"):
    did = str(uuid.uuid4())
    doc = {"id": did, "hash": did, "filename": "fixture.pdf", "status": status}
    store.save_document(doc)
    folder = store.directory / "documents" / did
    folder.mkdir()
    for filename in ("original.pdf", "parsed.md", "docling.json"):
        (folder / filename).write_text("Explicit synthetic cleanup fixture")
    store.save_chunks(did, [{"id": str(uuid.uuid4()), "document_id": did, "text": "fixture"}])
    return doc, folder


def seed_run(store, did, status="completed", question="Synthetic fixture question"):
    run = {
        "id": str(uuid.uuid4()),
        "created_at": now(),
        "status": status,
        "question": question,
        "document_ids": [did],
        "evidence": [{"id": "chunk-fixture", "document_id": did, "text": "saved evidence"}],
        "citations": [{"id": "chunk-fixture", "document_id": did, "page": 2}],
        "prompt": ["Original saved prompt"],
        "raw_response": "Original saved completion",
    }
    store.save_run(run)
    return run


def test_document_cleanup_removes_artifacts_preserves_history_and_other_document(
    tmp_path, monkeypatch
):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    store = app.state.store
    first, folder = seed_document(store)
    second, other_folder = seed_document(store)
    record = seed_run(store, first["id"])
    calls = []
    monkeypatch.setattr(app.state.pipeline.index, "delete_document", calls.append)
    with TestClient(app) as client:
        response = client.delete(f"/api/documents/{first['id']}")
        assert response.json() == {
            "kind": "documents",
            "deleted_ids": [first["id"]],
            "failures": [],
        }
        assert calls == [first["id"]]
        assert not folder.exists() and store.document(first["id"]) is None
        assert store.chunks(first["id"]) == []
        assert store.document(second["id"]) == second and other_folder.exists()
        assert client.get(f"/api/documents/{first['id']}/pdf").status_code == 404
        saved = client.get(f"/api/runs/{record['id']}").json()
        assert saved["missing_document_ids"] == [first["id"]]
        assert saved["citations"][0]["source_available"] is False
        assert saved["evidence"][0]["text"] == "saved evidence"
        assert (
            store.run(record["id"]) == record
        )  # Availability does not alter the original snapshot.
        assert client.delete(f"/api/documents/{first['id']}").status_code == 404
    reopened = Store(tmp_path)
    assert reopened.document(first["id"]) is None
    assert reopened.run(record["id"]) == record


def test_unreachable_qdrant_keeps_local_data_for_retry(tmp_path, monkeypatch):
    # Real TCP connection refusal; no model or vector responses are mocked for this failure.
    app = create_app(Settings(ragglass_data_dir=tmp_path, qdrant_url="http://127.0.0.1:1"))
    store = app.state.store
    doc, folder = seed_document(store)
    with TestClient(app) as client:
        failed = client.delete(f"/api/documents/{doc['id']}").json()
        assert not failed["deleted_ids"]
        assert failed["failures"][0]["code"] == "qdrant_cleanup_failed"
        assert "QDRANT_URL" in failed["failures"][0]["message"]
        assert (folder / "original.pdf").exists() and store.chunks(doc["id"])
        assert store.document(doc["id"])["status"] == "delete_failed"
        # Retry contract uses an explicit synthetic successful vector adapter.
        monkeypatch.setattr(app.state.pipeline.index, "delete_document", lambda _: None)
        assert client.delete(f"/api/documents/{doc['id']}").json()["deleted_ids"] == [doc["id"]]
        assert not folder.exists()


def test_busy_work_and_confirmation_count_are_protected(tmp_path, monkeypatch):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    pipeline = app.state.pipeline
    store = app.state.store
    doc, folder = seed_document(store)
    calls = []
    monkeypatch.setattr(pipeline.index, "delete_document", calls.append)
    with TestClient(app) as client:
        with pipeline.workspace.activity([doc["id"]], query=True):
            assert (
                client.delete(f"/api/documents/{doc['id']}").json()["detail"]["code"]
                == "cleanup_busy"
            )
            blocked = client.post("/api/runs/cleanup", json={"all": True, "expected_count": 0})
            assert blocked.status_code == 409
        doc["status"] = "queued"
        store.save_document(doc)
        assert client.delete(f"/api/documents/{doc['id']}").status_code == 409
        doc["status"] = "ready"
        store.save_document(doc)
        changed = client.post("/api/documents/cleanup", json={"all": True, "expected_count": 0})
        assert changed.json()["detail"]["code"] == "cleanup_count_changed"
        assert client.post("/api/documents/cleanup", json={"all": True}).status_code == 422
        assert client.post("/api/documents/cleanup", json={"ids": []}).status_code == 422
        assert (
            client.post(
                "/api/documents/cleanup", json={"ids": [doc["id"]], "all": True}
            ).status_code
            == 422
        )
        running = seed_run(store, doc["id"], status="running")
        assert client.delete(f"/api/runs/{running['id']}").status_code == 409
        assert folder.exists() and calls == []


def test_history_search_pagination_and_clear_all_exceed_default_list(tmp_path, monkeypatch):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    store = app.state.store
    doc, folder = seed_document(store)
    records = [seed_run(store, doc["id"], question=f"Fixture {i}") for i in range(125)]
    literal = seed_run(store, doc["id"], status="failed", question="100%_literal")
    monkeypatch.setattr(
        app.state.pipeline.index,
        "delete_document",
        lambda _: (_ for _ in ()).throw(AssertionError()),
    )
    with TestClient(app) as client:
        assert len(client.get("/api/runs").json()) == 100
        catalog = client.get("/api/runs/catalog", params={"offset": 100, "limit": 50}).json()
        assert catalog["total"] == 126 and len(catalog["items"]) == 26
        assert all("prompt" not in item for item in catalog["items"])
        filtered = client.get(
            "/api/runs/catalog", params={"search": "%_", "status": "failed"}
        ).json()
        assert filtered["matched"] == 1 and filtered["items"][0]["id"] == literal["id"]
        assert client.delete(f"/api/runs/{literal['id']}").json()["deleted_ids"] == [literal["id"]]
        selected = client.post(
            "/api/runs/cleanup", json={"ids": [records[0]["id"], records[1]["id"]]}
        ).json()
        assert len(selected["deleted_ids"]) == 2
        cleared = client.post("/api/runs/cleanup", json={"all": True, "expected_count": 123}).json()
        assert len(cleared["deleted_ids"]) == 123 and not cleared["failures"]
        assert store.run_states() == {} and folder.exists()
        assert client.get("/api/runs/catalog").json()["total"] == 0
    assert Store(tmp_path).run_states() == {} and Store(tmp_path).document(doc["id"])


def test_cleanup_removes_only_matching_document_vectors_in_all_ragglass_collections(
    tmp_path, monkeypatch
):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    index = app.state.pipeline.index
    calls = []
    monkeypatch.setattr(
        index.client,
        "get_collections",
        lambda: SimpleNamespace(
            collections=[
                SimpleNamespace(name="ragglass_current"),
                SimpleNamespace(name="ragglass_old"),
                SimpleNamespace(name="unrelated_collection"),
            ]
        ),
    )
    monkeypatch.setattr(
        index.client, "delete", lambda name, selector, **kw: calls.append((name, selector, kw))
    )
    index.delete_document("document-fixture")
    assert [c[0] for c in calls] == ["ragglass_current", "ragglass_old"]
    assert all(c[1].filter.must[0].key == "document_id" for c in calls)
    assert all(c[1].filter.must[0].match.value == "document-fixture" for c in calls)
    assert all(c[2] == {"wait": True} for c in calls)
    index.client.close()


def test_symlink_path_and_interrupted_deletion_are_safe(tmp_path, monkeypatch):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    doc, folder = seed_document(app.state.store)
    import shutil

    shutil.rmtree(folder)
    outside = tmp_path / "keep"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    folder.symlink_to(outside, target_is_directory=True)
    calls = []
    monkeypatch.setattr(app.state.pipeline.index, "delete_document", calls.append)
    with TestClient(app) as client:
        response = client.delete(f"/api/documents/{doc['id']}")
        assert response.json()["detail"]["code"] == "cleanup_invalid_path"
        assert (outside / "keep.txt").exists() and calls == []
    doc["status"] = "deleting"
    app.state.store.save_document(doc)
    Store(tmp_path).recover_interrupted()
    assert app.state.store.document(doc["id"])["status"] == "delete_failed"
    assert "清理" in app.state.store.document(doc["id"])["error"]
