"""Verify usability against an isolated real API/Qdrant and the configured model service."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ragglass.config import Settings  # noqa: E402
from ragglass.store import now  # noqa: E402


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def owner_snapshot(directory):
    paths = [*directory.glob("ragglass.sqlite3*"), *(directory / "documents").rglob("*")]
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file()
    }


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
        return "GPU telemetry unavailable"


def wait_run(client, rid):
    stages = []
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        response = client.get(f"runs/{rid}")
        response.raise_for_status()
        run = response.json()
        if run.get("stage") not in stages:
            stages.append(run.get("stage"))
        if run["status"] != "running":
            return run, stages
        time.sleep(0.05)
    raise TimeoutError("Real query did not finish")


def main(browser, workflows=False):
    settings = Settings()
    before = owner_snapshot(settings.ragglass_data_dir)
    (ROOT / ".data").mkdir(exist_ok=True)
    report = {"checked_at": now(), "mock": False, "gpu_before": gpu(), "runs": [], "checks": []}
    report["git_head"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    report["source_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in [ROOT / "backend/ragglass", ROOT / "frontend/src"]
        for path in folder.iterdir()
        if path.suffix in {".py", ".vue", ".ts", ".css"}
    }
    name = "ragglass-usability-" + uuid.uuid4().hex[:12]
    qdrant_port, api_port = port(), port()
    assert qdrant_port != api_port
    base = f"http://127.0.0.1:{api_port}"
    process = None
    created = False
    with TemporaryDirectory(prefix="usability-", dir=ROOT / ".data") as temporary:
        directory = Path(temporary)
        log = (ROOT / ".data/usability-server.log").open("wb")
        env = {
            **os.environ,
            "RAGGLASS_DATA_DIR": str(directory),
            "QDRANT_URL": f"http://127.0.0.1:{qdrant_port}",
            "QDRANT_API_KEY": "",
        }

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
                    str(api_port),
                ],
                cwd=ROOT,
                env={**env, **(overrides or {})},
                stdout=log,
                stderr=log,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Disposable API failed; see .data/usability-server.log")
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

        def checked(message):
            report["checks"].append(message)
            print("PASS " + message, flush=True)

        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    name,
                    "--publish",
                    f"127.0.0.1:{qdrant_port}:6333",
                    "--env",
                    "QDRANT__TELEMETRY_DISABLED=true",
                    "qdrant/qdrant:v1.15.5",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            created = True
            start()
            with httpx.Client(base_url=base + "/api/", timeout=240, trust_env=False) as client:
                assert client.get("health").json()["dependencies"] == {
                    "qdrant": "ready",
                    "llm": "ready",
                }
                assert client.get("documents").json() == []
                fixture = ROOT / "examples/ragglass-field-guide.pdf"
                with fixture.open("rb") as file:
                    response = client.post(
                        "documents", files={"file": (fixture.name, file, "application/pdf")}
                    )
                response.raise_for_status()
                doc = response.json()
                deadline = time.monotonic() + 600
                while doc["status"] not in {"ready", "failed"}:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Real native PDF indexing exceeded 600 seconds")
                    time.sleep(1)
                    doc = client.get(f"documents/{doc['id']}").json()
                assert doc["status"] == "ready", doc.get("error")
                report["document"] = doc
                checked(f"real Docling/E5/Qdrant indexing: {doc['timings_ms']['total']} ms")
                request = {"document_ids": [doc["id"]], "top_k": 5, "score_threshold": 0.7}
                for case in json.loads((ROOT / "examples/questions.json").read_text()):
                    response = client.post("query", json={**request, "question": case["question"]})
                    response.raise_for_status()
                    run = response.json()
                    assert run["status"] == "completed", run.get("error")
                    assert run["answerable"] == case["answerable"], run.get("answer")
                    if case["answerable"]:
                        assert case["expected_text"].lower() in run["answer"].lower()
                        assert any(case["expected_page"] in c["pages"] for c in run["citations"])
                    else:
                        assert not run["citations"]
                    assert all(
                        c["id"] in {e["id"] for e in run["evidence"]} for c in run["citations"]
                    )
                    assert run["raw_response"] and run["model_metrics"]
                    report["runs"].append({"case": case, "run": run})
                    checked(
                        f"live legacy API: {case['question']} ({run['timings_ms']['total']} ms)"
                    )
                if workflows:
                    from verify_workflows import check_workflows

                    check_workflows(client, doc, report, checked, ROOT, directory, wait_run)
                response = client.post(
                    "query/start",
                    json={
                        **request,
                        "question": "What is the maximum upload size for the Cedar pilot?",
                    },
                )
                assert response.status_code == 202
                run, stages = wait_run(client, response.json()["id"])
                assert run["status"] == "completed" and "30 MB" in run["answer"]
                assert "generation" in stages and run["citations"]
                report["async_run"] = {"run": run, "observed_stages": stages}
                checked(
                    "live asynchronous progress and validated answer: "
                    f"{run['timings_ms']['total']} ms"
                )
                response = client.post(
                    "query/start",
                    json={
                        **request,
                        "score_threshold": 0,
                        "question": (
                            "Summarize every configuration limit and default in the Cedar pilot, "
                            "citing the document."
                        ),
                    },
                )
                response.raise_for_status()
                rid = response.json()["id"]
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    pending = client.get(f"runs/{rid}").json()
                    if pending["stage"] == "generation":
                        break
                    assert pending["status"] == "running", pending
                    time.sleep(0.01)
                else:
                    raise TimeoutError("Cancellation did not reach model generation")
                response = client.post(f"runs/{rid}/cancel")
                response.raise_for_status()
                stopped, stages = wait_run(client, rid)
                assert (
                    stopped["status"] == "cancelled" and stopped["evidence"] and stopped["prompt"]
                )
                assert stopped["answer"] is None and not stopped["citations"]
                assert client.post(f"runs/{rid}/cancel").json() == stopped
                assert client.get("runs/catalog?status=cancelled").json()["matched"] == (
                    2 if workflows else 1
                )
                report["cancelled_run"] = stopped
                checked(
                    "real generation cancellation retains evidence: "
                    f"{stopped['timings_ms']['total']} ms"
                )
                stop()
                start({"LLM_BASE_URL": "http://127.0.0.1:1", "LLM_TIMEOUT_SECONDS": "1"})
                response = client.post(
                    "query/start",
                    json={
                        **request,
                        "question": "What is the maximum upload size for the Cedar pilot?",
                    },
                )
                response.raise_for_status()
                failed, _ = wait_run(client, response.json()["id"])
                assert failed["status"] == "failed" and failed["error_code"] == "llm_unavailable"
                assert failed["evidence"] and failed["prompt"] and not failed["answer"]
                report["connection_failure"] = failed
                checked("actual model TCP refusal keeps evidence and actionable error")
                stop()
                start()
                assert client.get(f"runs/{rid}").json() == stopped
                checked("actual API restart preserves cancelled query, prompt and evidence")
                if workflows:
                    stopped_summary = report["workflows"]["cancelled_summary"]
                    assert client.get(f"runs/{stopped_summary['id']}").json() == stopped_summary
                    checked(
                        "actual API restart preserves cancelled summary nodes and model-call trace"
                    )
                if browser:
                    started = time.perf_counter()
                    completed = subprocess.run(
                        [
                            "npm",
                            "--prefix",
                            "frontend",
                            "run",
                            "test:e2e",
                            "--",
                            "workbench.spec.ts",
                            "usability.spec.ts",
                            *(["workflows.spec.ts"] if workflows else []),
                        ],
                        cwd=ROOT,
                        env={
                            **os.environ,
                            "RAGGLASS_BASE_URL": base,
                            **(
                                {
                                    "RAGGLASS_SUMMARY_DOCUMENT_ID": report["workflows"][
                                        "complaint_document"
                                    ]["id"]
                                }
                                if workflows
                                else {}
                            ),
                        },
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    )
                    (ROOT / ".data/usability-browser.log").write_text(completed.stdout)
                    print(completed.stdout, flush=True)
                    completed.check_returncode()
                    report["browser_wall_seconds"] = round(time.perf_counter() - started, 2)
                    checked(
                        "built Chrome checks: real PDF/tools/clipboard/export, "
                        "live inference, synthetic lifecycle"
                    )
                    for kind in ("runs", "documents"):
                        count = len(client.get(kind).json())
                        response = client.post(
                            f"{kind}/cleanup", json={"all": True, "expected_count": count}
                        )
                        response.raise_for_status()
                        assert not response.json()["failures"]
                    completed = subprocess.run(
                        ["npm", "--prefix", "frontend", "run", "test:e2e", "--", "cleanup.spec.ts"],
                        cwd=ROOT,
                        env={**os.environ, "RAGGLASS_BASE_URL": base, "RAGGLASS_CLEANUP_TEST": "1"},
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    )
                    (ROOT / ".data/usability-cleanup-browser.log").write_text(completed.stdout)
                    print(completed.stdout, flush=True)
                    completed.check_returncode()
                    checked("built Chrome cleanup regression in the disposable workspace")
                report["gpu_after"] = gpu()
                report["completed"] = True
        finally:
            stop()
            log.close()
            if created:
                subprocess.run(["docker", "rm", "--force", name], check=True, capture_output=True)
            report["owner_workspace_unchanged"] = (
                owner_snapshot(settings.ragglass_data_dir) == before
            )
            if not report.get("completed"):
                failure_path = ROOT / (
                    ".data/workflows-verification.failed.json"
                    if workflows
                    else ".data/usability-verification.failed.json"
                )
                failure_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    report["owner_workspace_unchanged"] = owner_snapshot(settings.ragglass_data_dir) == before
    assert report["owner_workspace_unchanged"]
    checked("owner documents and SQLite unchanged; owned API/Qdrant stopped and removed")
    report_path = ROOT / (
        ".data/workflows-verification.json" if workflows else ".data/usability-verification.json"
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Measured report: {report_path.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true", help="Run built Chrome usability checks")
    main(parser.parse_args().browser)
