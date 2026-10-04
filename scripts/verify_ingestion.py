"""Verify upload checks, cancellation and batched indexing in an owned real stack."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from pypdf import PdfReader, PdfWriter
from qdrant_client import QdrantClient, models
from verify_usability import gpu, owner_snapshot, port

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ragglass.config import Settings  # noqa: E402
from ragglass.store import now  # noqa: E402


def pdf_bytes(writer):
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def variant(data, name):
    writer = PdfWriter(clone_from=BytesIO(data))
    writer.add_metadata({"/Subject": f"Fictional CC0 RAGGlass verification: {name}"})
    return pdf_bytes(writer)


def browser_check(suites, environment, filename):
    command = ["npm", "--prefix", "frontend", "run", "test:e2e", "--", *suites]
    started = time.perf_counter()
    with (ROOT / ".data" / filename).open("w") as log:
        with subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ) as browser:
            for line in browser.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            if browser.wait() != 0:
                raise subprocess.CalledProcessError(browser.returncode, command)
    return round(time.perf_counter() - started, 2)


def main(browser):
    settings = Settings()
    settings.configure_paths()
    before = owner_snapshot(settings.ragglass_data_dir)
    (ROOT / ".data").mkdir(exist_ok=True)
    report = {
        "checked_at": now(),
        "mock": False,
        "gpu_before": gpu(),
        "checks": [],
        "documents": [],
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in [ROOT / "backend/ragglass", ROOT / "frontend/src"]
            for path in folder.iterdir()
            if path.suffix in {".py", ".vue", ".ts", ".css"}
        },
    }
    name = "ragglass-ingestion-" + uuid.uuid4().hex[:12]
    qport, aport = port(), port()
    assert qport != aport
    base = f"http://127.0.0.1:{aport}"
    process, created = None, False
    with TemporaryDirectory(prefix="ingestion-", dir=ROOT / ".data") as temporary:
        directory = Path(temporary)
        fixtures = directory / "fixtures"
        fixtures.mkdir()
        log = (ROOT / ".data/ingestion-server.log").open("wb")
        env = {
            **os.environ,
            "RAGGLASS_DATA_DIR": str(directory / "workspace"),
            "QDRANT_URL": f"http://127.0.0.1:{qport}",
            "QDRANT_API_KEY": "",
            "MAX_UPLOAD_MB": "30",
            "MAX_PDF_PAGES": "200",
            "INGEST_BATCH_SIZE": "2",
        }

        def checked(message):
            report["checks"].append(message)
            print("PASS " + message, flush=True)

        def start():
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
                    str(aport),
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Disposable API failed; see .data/ingestion-server.log")
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
                process.wait(timeout=60)

        def rss():
            # API process VmHWM includes model loading and all work, not vector-only memory.
            for line in Path(f"/proc/{process.pid}/status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    report["api_peak_rss_kib"] = max(
                        report.get("api_peak_rss_kib", 0), int(line.split()[1])
                    )

        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    name,
                    "--publish",
                    f"127.0.0.1:{qport}:6333",
                    "--env",
                    "QDRANT__TELEMETRY_DISABLED=true",
                    "qdrant/qdrant:v1.15.5",
                ],
                check=True,
                capture_output=True,
            )
            created = True
            start()
            vectors = QdrantClient(url=env["QDRANT_URL"])
            with httpx.Client(base_url=base + "/api/", timeout=240, trust_env=False) as client:
                assert client.get("health").json()["dependencies"] == {
                    "qdrant": "ready",
                    "llm": "ready",
                }
                data = (ROOT / "examples/ragglass-field-guide.pdf").read_bytes()
                blank = PdfWriter()
                blank.add_blank_page(width=200, height=200)
                encrypted = PdfWriter(clone_from=BytesIO(data))
                encrypted.encrypt("fixture-password")
                many = PdfWriter()
                for _ in range(201):
                    many.add_blank_page(width=200, height=200)
                for filename, contents in {
                    "invalid.pdf": b"not a PDF",
                    "blank.pdf": pdf_bytes(blank),
                    "encrypted.pdf": pdf_bytes(encrypted),
                    "too-many-pages.pdf": pdf_bytes(many),
                    "browser-native.pdf": variant(data, "browser cancellation"),
                }.items():
                    (fixtures / filename).write_bytes(contents)
                for filename in ["invalid.pdf", "blank.pdf", "encrypted.pdf", "too-many-pages.pdf"]:
                    response = client.post(
                        "documents", files={"file": (filename, (fixtures / filename).read_bytes())}
                    )
                    assert response.status_code == 422, response.text
                response = client.post(
                    "documents", files={"file": ("large.pdf", b"%PDF-" + b"0" * (30 * 1024**2))}
                )
                assert response.status_code == 413
                assert client.get("documents").json() == []
                checked(
                    "actual upload rejects invalid, encrypted, no-text, over-page and "
                    "over-size PDFs without records"
                )

                def upload(contents, filename):
                    started = time.perf_counter()
                    response = client.post(
                        "documents", files={"file": (filename, contents, "application/pdf")}
                    )
                    response.raise_for_status()
                    doc = response.json()
                    report.setdefault("upload_response_ms", []).append(
                        round((time.perf_counter() - started) * 1000, 2)
                    )
                    assert response.status_code == 202 and doc["status"] == "queued"
                    return doc

                def wait_doc(did, predicate=None):
                    observations = []
                    deadline = time.monotonic() + 600
                    while time.monotonic() < deadline:
                        response = client.get(f"documents/{did}")
                        response.raise_for_status()
                        doc = response.json()
                        observation = {"status": doc["status"], "progress": doc.get("progress")}
                        if not observations or observations[-1] != observation:
                            observations.append(observation)
                        rss()
                        if predicate and predicate(doc):
                            return doc, observations
                        if doc["status"] in {"ready", "failed", "cancelled"}:
                            if predicate:
                                raise AssertionError(
                                    f"Job terminated before requested stage: {doc['status']}"
                                )
                            return doc, observations
                        time.sleep(0.01)
                    raise TimeoutError("Real document processing exceeded 600 seconds")

                def count(doc):
                    return vectors.count(
                        doc.get("partial_index_collection", doc.get("collection")),
                        count_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="document_id",
                                    match=models.MatchValue(value=doc["id"]),
                                )
                            ]
                        ),
                        exact=True,
                    ).count

                original = upload(data, "ragglass-field-guide.pdf")
                doc, observations = wait_doc(original["id"])
                assert doc["status"] == "ready", doc.get("error")
                assert doc["progress"]["indexed_chunks"] == doc["chunk_count"] == count(doc)
                assert doc["chunk_count"] > 2
                report["documents"].append({"document": doc, "observations": observations})
                checked(
                    f"real Docling/E5/Qdrant batches: {doc['chunk_count']} chunks, "
                    f"{doc['timings_ms']['total']} ms"
                )
                duplicate = client.post("documents", files={"file": ("same.pdf", data)}).json()
                assert duplicate["duplicate"] and duplicate["id"] == doc["id"]
                assert duplicate["progress"] == doc["progress"]
                checked("duplicate native PDF reuses ID and completed index")

                writer = PdfWriter()
                reader = PdfReader(BytesIO(data))
                for _ in range(8):
                    for page in reader.pages:
                        writer.add_page(page)
                writer.add_metadata({"/Subject": "Fictional CC0 24-page ingestion stress fixture"})
                long_doc = upload(pdf_bytes(writer), "public-long-fixture.pdf")
                wait_doc(long_doc["id"], lambda d: d["status"] == "parsing")
                queued = upload(variant(data, "queued cancellation"), "queued-native.pdf")
                assert client.delete(f"documents/{queued['id']}").status_code == 409
                queued_stop = client.post(f"documents/{queued['id']}/cancel").json()
                assert queued_stop["status"] == "cancelled" and queued_stop["cancel_requested"]
                assert client.post(f"documents/{queued['id']}/cancel").json() == queued_stop
                assert client.get(f"documents/{queued['id']}/chunks").json() == []
                assert not (
                    directory / "workspace/documents" / queued["id"] / "docling.json"
                ).exists()
                report["queued_cancellation"] = queued_stop
                checked(
                    "real queued cancellation keeps original PDF and runs no parser or embedding"
                )
                pending, observations = wait_doc(
                    long_doc["id"],
                    lambda d: 0
                    < d["progress"]["indexed_chunks"]
                    < (d["progress"]["total_chunks"] or 0),
                )
                assert (
                    client.post(
                        "query/start",
                        json={"question": "Upload limit?", "document_ids": [long_doc["id"]]},
                    ).status_code
                    == 409
                )
                requested = client.post(f"documents/{long_doc['id']}/cancel")
                requested.raise_for_status()
                cancelled, after_stop = wait_doc(long_doc["id"])
                assert cancelled["status"] == "cancelled"
                assert 0 < cancelled["progress"]["indexed_chunks"] < cancelled["chunk_count"]
                assert count(cancelled) == cancelled["progress"]["indexed_chunks"]
                assert client.get(f"documents/{long_doc['id']}/pdf").status_code == 200
                report["active_cancellation"] = {
                    "document": cancelled,
                    "observations": observations + after_stop,
                    "requested_after": pending,
                }
                checked(
                    f"real batch cancellation retains {count(cancelled)} confirmed chunks "
                    "and excludes unfinished document from queries"
                )
                stop()
                # Verify the production default on the complete 24-page rebuild.
                env["INGEST_BATCH_SIZE"] = "32"
                start()
                assert client.get(f"documents/{long_doc['id']}").json() == cancelled
                assert client.get(f"documents/{queued['id']}").json() == queued_stop
                checked("actual API restart preserves both cancelled records and progress")
                response = client.post(f"documents/{long_doc['id']}/reindex")
                response.raise_for_status()
                restored, observations = wait_doc(long_doc["id"])
                assert restored["status"] == "ready" and not restored["cancel_requested"]
                assert restored["ingestion"]["vector_batch_size"] == 32
                assert (
                    restored["progress"]["indexed_chunks"]
                    == restored["chunk_count"]
                    == count(restored)
                )
                report["documents"].append({"document": restored, "observations": observations})
                checked(
                    f"real 24-page reindex: {restored['chunk_count']} chunks, "
                    f"{restored['timings_ms']['total']} ms"
                )
                report["runs"] = []
                for case in json.loads((ROOT / "examples/questions.json").read_text()):
                    response = client.post(
                        "query",
                        json={
                            "question": case["question"],
                            "document_ids": [doc["id"]],
                            "top_k": 5,
                            "score_threshold": 0.7,
                        },
                    )
                    response.raise_for_status()
                    run = response.json()
                    assert (
                        run["status"] == "completed" and run["answerable"] == case["answerable"]
                    ), run.get("error")
                    if case["answerable"]:
                        assert case["expected_text"].lower() in run["answer"].lower()
                        assert any(
                            case["expected_page"] in citation["pages"]
                            for citation in run["citations"]
                        )
                    else:
                        assert not run["citations"]
                    assert all(
                        c["id"] in {e["id"] for e in run["evidence"]} for c in run["citations"]
                    )
                    report["runs"].append({"case": case, "run": run})
                    checked(f"live model: {case['question']} ({run['timings_ms']['total']} ms)")
                if browser:
                    report["browser_wall_seconds"] = browser_check(
                        ["ingestion.spec.ts", "workbench.spec.ts", "usability.spec.ts"],
                        {
                            **os.environ,
                            "RAGGLASS_BASE_URL": base,
                            "RAGGLASS_INGESTION_FIXTURES_DIR": str(fixtures),
                        },
                        "ingestion-browser.log",
                    )
                    checked(
                        "built Chrome: real preflight/stop/reindex/source, PDF/query tools, "
                        "synthetic progress contracts"
                    )
                    for kind in ("runs", "documents"):
                        total = (
                            client.get("runs/catalog").json()["total"]
                            if kind == "runs"
                            else len(client.get("documents").json())
                        )
                        response = client.post(
                            f"{kind}/cleanup", json={"all": True, "expected_count": total}
                        )
                        response.raise_for_status()
                        assert not response.json()["failures"]
                    report["cleanup_browser_wall_seconds"] = browser_check(
                        ["cleanup.spec.ts"],
                        {**os.environ, "RAGGLASS_BASE_URL": base, "RAGGLASS_CLEANUP_TEST": "1"},
                        "ingestion-cleanup-browser.log",
                    )
                    checked("built Chrome cleanup regression in owned fresh workspace")
                report["gpu_after"] = gpu()
            vectors.close()
        finally:
            stop()
            log.close()
            if created:
                subprocess.run(["docker", "rm", "--force", name], check=True, capture_output=True)
    report["owner_workspace_unchanged"] = owner_snapshot(settings.ragglass_data_dir) == before
    assert report["owner_workspace_unchanged"]
    checked("owner data unchanged; owned API and Qdrant stopped and removed")
    (ROOT / ".data/ingestion-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print("Measured report: .data/ingestion-verification.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    main(parser.parse_args().browser)
