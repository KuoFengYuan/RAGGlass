"""Exercise the running real stack. Write only measured results to .data/verification.json."""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("RAGGLASS_BASE_URL", "http://127.0.0.1:8000").rstrip("/") + "/api"


def gpu():
    try:
        return subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "NVIDIA GPU telemetry unavailable on this host"


def main():
    fixture = ROOT / "examples" / "ragglass-field-guide.pdf"
    reader = PdfReader(fixture)
    assert len(reader.pages) == 3
    assert "Mira Chen" in reader.pages[0].extract_text()
    assert "30 MB" in reader.pages[1].extract_text()
    report = {"mock": False, "api": API, "gpu_before": gpu(), "questions": []}
    with httpx.Client(timeout=240, trust_env=False) as client:
        assert client.get(f"{API}/health").json()["dependencies"] == {
            "qdrant": "ready",
            "llm": "ready",
        }
        with fixture.open("rb") as file:
            response = client.post(
                f"{API}/documents", files={"file": (fixture.name, file, "application/pdf")}
            )
        response.raise_for_status()
        doc = response.json()
        if doc["status"] == "failed":
            response = client.post(f"{API}/documents/{doc['id']}/reindex")
            response.raise_for_status()
            doc = response.json()
        deadline = time.monotonic() + 600
        while doc["status"] not in {"ready", "failed"}:
            if time.monotonic() > deadline:
                raise TimeoutError("PDF ingestion exceeded 600s")
            time.sleep(1)
            doc = client.get(f"{API}/documents/{doc['id']}").json()
        assert doc["status"] == "ready", doc.get("error")
        report["document"] = doc
        chunks = client.get(f"{API}/documents/{doc['id']}/chunks").json()
        assert all(1 <= c["page"] <= 3 and c["document_hash"] == doc["hash"] for c in chunks)
        assert any(c["page"] == 2 and "30 MB" in c["text"] for c in chunks)
        assert any(c["page"] == 1 and "Mira Chen" in c["text"] for c in chunks)
        assert all(c["coordinates_available"] and c["provenance"] for c in chunks)
        for test in json.loads((ROOT / "examples" / "questions.json").read_text()):
            result = client.post(
                f"{API}/query",
                json={
                    "question": test["question"],
                    "document_ids": [doc["id"]],
                    "top_k": 5,
                    "score_threshold": 0.70,
                },
            )
            result.raise_for_status()
            run = result.json()
            assert run["status"] == "completed", run.get("error")
            assert run["answerable"] == test["answerable"], run["answer"]
            if test["answerable"]:
                assert test["expected_text"].lower() in run["answer"].lower(), run["answer"]
                assert any(
                    c["page"] == test["expected_page"]
                    and test["expected_text"].lower() in c["text"].lower()
                    for c in run["evidence"]
                )
                assert any(test["expected_page"] in c["pages"] for c in run["citations"])
            else:
                assert not run["citations"]
            allowed = {c["id"] for c in run["evidence"]}
            assert all(
                c["id"] in allowed and c["document_id"] == doc["id"] for c in run["citations"]
            )
            assert run["prompt"] and run["raw_response"] and run["model_metrics"]
            report["questions"].append({"test": test, "run": run})
            print(
                f"PASS {test['question']} -> {run['answer']} ({run['timings_ms']['total']} ms)",
                flush=True,
            )
        # Switch only this application's LLM adapter to an unreachable endpoint.
        # Done in unit/API contract tests, never by stopping the shared model service.
        report["gpu_after"] = gpu()
        report["model_service"] = client.get("http://127.0.0.1:11434/api/ps").json()
        output = ROOT / ".data" / "verification.json"
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Measured verification record: {output}", flush=True)


if __name__ == "__main__":
    main()
