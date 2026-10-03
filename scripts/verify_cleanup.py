"""Check real cleanup in an owned disposable API; never clear the user's workspace."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from pypdf import PdfWriter
from qdrant_client import QdrantClient, models

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ragglass.config import Settings  # noqa: E402
from ragglass.store import Store, now  # noqa: E402


def document_filter(did):
    return models.Filter(
        must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=did))]
    )


def main(browser_checks):
    (ROOT / ".data").mkdir(exist_ok=True)
    settings = Settings()
    original = Store(settings.ragglass_data_dir)
    original_docs = [d["id"] for d in original.documents()]
    original_runs = original.run_states()
    vectors = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    original_counts = {
        c.name: vectors.count(
            c.name,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchAny(any=original_docs)
                    )
                ]
            ),
            exact=True,
        ).count
        for c in vectors.get_collections().collections
        if c.name.startswith("ragglass_") and original_docs
    }
    report = {"checked_at": now(), "mock": False, "checks": [], "runs": [], "documents": []}
    own_ids = set()
    old_collection = "ragglass_cleanup_" + uuid.uuid4().hex
    process = None
    with TemporaryDirectory(prefix="cleanup-", dir=ROOT / ".data") as temporary:
        directory = Path(temporary)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        environment = {**os.environ, "RAGGLASS_DATA_DIR": str(directory)}
        log = (directory / "server.log").open("ab")

        def start(overrides=None):
            nonlocal process
            process = subprocess.Popen(
                [
                    str(ROOT / ".venv/bin/python"),
                    "-m",
                    "uvicorn",
                    "ragglass.main:app",
                    "--app-dir",
                    "backend",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env={**environment, **(overrides or {})},
                stdout=log,
                stderr=log,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError((directory / "server.log").read_text()[-3000:])
                try:
                    if (
                        httpx.get(base + "/api/documents", timeout=1, trust_env=False).status_code
                        == 200
                    ):
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            raise TimeoutError("Disposable API did not start")

        def stop():
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=30)

        def checked(name):
            report["checks"].append(name)
            print("PASS " + name, flush=True)

        try:
            start()
            with httpx.Client(base_url=base + "/api/", timeout=240, trust_env=False) as client:
                assert client.get("health").json()["dependencies"] == {
                    "qdrant": "ready",
                    "llm": "ready",
                }
                assert (
                    client.get("documents").json() == []
                )  # Own fresh API, never a running user API.

                def upload(data, name):
                    response = client.post(
                        "documents", files={"file": (name, data, "application/pdf")}
                    )
                    response.raise_for_status()
                    doc = response.json()
                    own_ids.add(doc["id"])
                    deadline = time.monotonic() + 600
                    while doc["status"] not in {"ready", "failed"}:
                        if time.monotonic() > deadline:
                            raise TimeoutError("Real ingestion exceeded 600 seconds")
                        time.sleep(1)
                        doc = client.get(f"documents/{doc['id']}").json()
                    assert doc["status"] == "ready", doc.get("error")
                    report["documents"].append(doc)
                    print(
                        f"Indexed {name}: {doc['chunk_count']} chunks / "
                        f"{doc['timings_ms']['total']} ms",
                        flush=True,
                    )
                    return doc

                def ask(doc, question):
                    response = client.post(
                        "query",
                        json={
                            "question": question,
                            "document_ids": [doc["id"]],
                            "top_k": 5,
                            "score_threshold": 0.7,
                        },
                    )
                    response.raise_for_status()
                    run = response.json()
                    report["runs"].append(run)
                    print(f"Query {run['status']}: {run['timings_ms']['total']} ms", flush=True)
                    return run

                data = (ROOT / "examples/ragglass-field-guide.pdf").read_bytes()
                first = upload(data, "ragglass-field-guide.pdf")
                writer = PdfWriter(clone_from=BytesIO(data))
                writer.add_metadata({"/Subject": "Public CC0 cleanup verification variant"})
                variant = BytesIO()
                writer.write(variant)
                second = upload(variant.getvalue(), "cleanup-variant.pdf")
                current = first["collection"]
                chunks = client.get(f"documents/{first['id']}/chunks").json()
                assert any(c["page"] == 2 and "30 MB" in c["text"] for c in chunks)
                assert all(c["document_hash"] == first["hash"] and c["provenance"] for c in chunks)
                checked("real Docling/E5 indexing with native pages and table evidence")
                points = vectors.scroll(
                    current,
                    scroll_filter=document_filter(first["id"]),
                    limit=100,
                    with_vectors=True,
                )[0]
                vectors.create_collection(
                    old_collection,
                    vectors_config=models.VectorParams(
                        size=len(points[0].vector), distance=models.Distance.COSINE
                    ),
                )
                vectors.upsert(
                    old_collection,
                    [
                        models.PointStruct(id=p.id, vector=p.vector, payload=p.payload)
                        for p in points
                    ],
                    wait=True,
                )
                run = ask(first, "What is the maximum upload size for the Cedar pilot?")
                assert run["status"] == "completed" and "30 MB" in run["answer"]
                assert any(2 in c["pages"] for c in run["citations"])
                assert all(c["id"] in {e["id"] for e in run["evidence"]} for c in run["citations"])
                checked("real model answer with retrieved citations to original page 2")
                stop()
                start({"LLM_BASE_URL": "http://127.0.0.1:1", "LLM_TIMEOUT_SECONDS": "1"})
                failed = ask(first, "What is the maximum upload size for the Cedar pilot?")
                assert failed["status"] == "failed" and failed["error_code"] == "llm_unavailable"
                assert failed["evidence"] and failed["prompt"] and "LLM_BASE_URL" in failed["error"]
                checked("real model endpoint refusal retains evidence and actionable error")
                stop()
                start()
                assert client.get(f"runs/{run['id']}").json() == run
                before_second = vectors.count(
                    current, count_filter=document_filter(second["id"]), exact=True
                ).count
                response = client.delete(f"documents/{first['id']}").json()
                assert response["deleted_ids"] == [first["id"]] and not response["failures"]
                assert not (directory / "documents" / first["id"]).exists()
                assert client.get(f"documents/{first['id']}/pdf").status_code == 404
                assert Store(directory).chunks(first["id"]) == []
                for collection in (current, old_collection):
                    assert (
                        vectors.count(
                            collection, count_filter=document_filter(first["id"]), exact=True
                        ).count
                        == 0
                    )
                assert (
                    vectors.count(
                        current, count_filter=document_filter(second["id"]), exact=True
                    ).count
                    == before_second
                    > 0
                )
                kept = client.get(f"runs/{run['id']}").json()
                assert kept["answer"] == run["answer"] and kept["prompt"] == run["prompt"]
                assert kept["missing_document_ids"] == [first["id"]]
                assert all(c["source_available"] is False for c in kept["citations"])
                checked(
                    "PDF/files/chunks/vectors removed across embedding collections; "
                    "other PDF and saved history preserved"
                )
                assert client.delete(f"runs/{run['id']}").json()["deleted_ids"] == [run["id"]]
                assert client.get(f"runs/{run['id']}").status_code == 404
                assert client.get(f"documents/{second['id']}/pdf").status_code == 200
                assert client.post("runs/cleanup", json={"ids": [failed["id"]]}).json()[
                    "deleted_ids"
                ] == [failed["id"]]
                third = upload(data, "ragglass-field-guide.pdf")
                assert third["id"] != first["id"] and third["hash"] == first["hash"]
                checked(
                    "single/batch history removal preserves PDFs; "
                    "deleted hash can be uploaded with a new ID"
                )
                stop()
                start()
                assert client.get(f"runs/{run['id']}").status_code == 404
                assert len(client.get("documents").json()) == 2
                checked("deletions and remaining files persist after actual API restart")
                assert not client.post(
                    "documents/cleanup", json={"all": True, "expected_count": 2}
                ).json()["failures"]
                checked("clear all documents removes the whole disposable workspace")
                if browser_checks:
                    browser_env = {**os.environ, "RAGGLASS_BASE_URL": base}
                    subprocess.run(
                        [
                            "npm",
                            "--prefix",
                            "frontend",
                            "run",
                            "test:e2e",
                            "--",
                            "workbench.spec.ts",
                        ],
                        cwd=ROOT,
                        env=browser_env,
                        check=True,
                    )
                    for doc in client.get("documents").json():
                        own_ids.add(doc["id"])
                    # The browser fixture uses an empty, owned workspace.
                    for kind in ("runs", "documents"):
                        count = len(client.get(kind).json())
                        cleared = client.post(
                            f"{kind}/cleanup", json={"all": True, "expected_count": count}
                        ).json()
                        assert not cleared["failures"]
                    subprocess.run(
                        ["npm", "--prefix", "frontend", "run", "test:e2e", "--", "cleanup.spec.ts"],
                        cwd=ROOT,
                        env={**browser_env, "RAGGLASS_CLEANUP_TEST": "1"},
                        check=True,
                    )
                    checked(
                        "three built-UI Chrome tests with live inference, bilingual cleanup, "
                        "source handling and mobile confirmation"
                    )
                stop()
                start()
                assert client.get("documents").json() == []
                assert client.get("runs").json() == []
                checked("cleared documents/history stay empty after API restart")
        finally:
            stop()
            if vectors.collection_exists(old_collection):
                vectors.delete_collection(old_collection)
            # Clean up only IDs created by this script if a mid-run check fails.
            for doc in Store(directory).documents():
                own_ids.add(doc["id"])
            for collection in vectors.get_collections().collections:
                if collection.name.startswith("ragglass_") and own_ids:
                    vectors.delete(
                        collection.name,
                        models.FilterSelector(
                            filter=models.Filter(
                                must=[
                                    models.FieldCondition(
                                        key="document_id", match=models.MatchAny(any=list(own_ids))
                                    )
                                ]
                            )
                        ),
                        wait=True,
                    )
            log.close()
            (ROOT / ".data/cleanup-server.log").write_bytes((directory / "server.log").read_bytes())
    assert [d["id"] for d in original.documents()] == original_docs
    assert original.run_states() == original_runs
    for name, count in original_counts.items():
        assert (
            vectors.count(
                name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchAny(any=original_docs)
                        )
                    ]
                ),
                exact=True,
            ).count
            == count
        )
    vectors.close()
    checked("existing owner documents, run records and vectors unchanged")
    (ROOT / ".data/cleanup-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print("Measured report: .data/cleanup-verification.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Run Chrome checks and capture bilingual cleanup screens",
    )
    main(parser.parse_args().browser)
