"""Restart only this project's API/Qdrant and verify real persistent state (Linux)."""

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000/api"


def wait_ready(client, url, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = client.get(url)
            if response.status_code == 200:
                return response
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Service did not restart: {url}")


def main(pid):
    # Refuse to signal any process not explicitly identified as this project's API.
    proc = Path(f"/proc/{pid}")
    command = (proc / "cmdline").read_bytes().split(b"\0")
    assert b"ragglass.main:app" in command, "PID is not a RAGGlass API"
    assert (proc / "cwd").resolve() == ROOT, "PID belongs to a different project"
    with httpx.Client(timeout=240, trust_env=False) as client:
        docs = client.get(f"{API}/documents").json()
        runs = client.get(f"{API}/runs").json()
        sample = next(d for d in docs if d["filename"] == "ragglass-field-guide.pdf")
        assert sample["status"] == "ready" and runs
        saved = client.get(f"{API}/runs/{runs[0]['id']}").json()
        vectors_url = f"http://127.0.0.1:6333/collections/{sample['collection']}"
        count_before = client.get(vectors_url).json()["result"]["points_count"]
        print("Restarting verified RAGGlass API and project Qdrant container…", flush=True)
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 30
        while proc.exists() and time.monotonic() < deadline:
            # A exited/reaped process no longer owns the socket.
            try:
                if "State:\tZ" in (proc / "status").read_text():
                    break
            except FileNotFoundError:
                break
            time.sleep(0.1)
        if proc.exists() and "State:\tZ" not in (proc / "status").read_text():
            raise TimeoutError("API did not exit; no additional process was started")
        subprocess.run(["docker", "compose", "restart", "qdrant"], cwd=ROOT, check=True)
        wait_ready(client, "http://127.0.0.1:6333/readyz")
        log_path = ROOT / ".data" / "backend.log"
        with log_path.open("ab") as log:
            new_api = subprocess.Popen(
                [
                    str(ROOT / ".venv" / "bin" / "python"),
                    "-m",
                    "uvicorn",
                    "ragglass.main:app",
                    "--app-dir",
                    "backend",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        wait_ready(client, f"{API}/documents")
        assert client.get(f"{API}/documents").json() == docs
        assert client.get(f"{API}/runs/{saved['id']}").json() == saved
        count_after = client.get(vectors_url).json()["result"]["points_count"]
        assert count_after == count_before
        response = client.post(
            f"{API}/query",
            json={
                "question": "What is the maximum upload size for the Cedar pilot?",
                "document_ids": [sample["id"]],
                "top_k": 5,
                "score_threshold": 0.70,
            },
        )
        response.raise_for_status()
        run = response.json()
        assert run["status"] == "completed" and "30 MB" in run["answer"]
        assert any(c["page"] == 2 for c in run["citations"])
        assert client.get("http://127.0.0.1:8000/").status_code == 200
        report = {
            "mock": False,
            "old_api_pid": pid,
            "new_api_pid": new_api.pid,
            "preserved_document_ids": [d["id"] for d in docs],
            "preserved_run_ids": [r["id"] for r in runs],
            "qdrant_points_before": count_before,
            "qdrant_points_after": count_after,
            "post_restart_run": run,
        }
        (ROOT / ".data" / "restart-verification.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            f"PASS API PID {pid} → {new_api.pid}; documents, history, vectors preserved", flush=True
        )
        print(f"PASS built UI and post-restart real answer: {run['answer']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-pid", type=int, required=True)
    main(parser.parse_args().api_pid)
