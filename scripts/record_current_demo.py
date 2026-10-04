"""Own a disposable real stack for fresh demo footage; always remove only its services."""

import hashlib
import json
import os
import socket
import subprocess
import time
import uuid
from tempfile import TemporaryDirectory

import httpx
from verify_usability import ROOT, Settings, owner_snapshot, port


def main():
    settings = Settings()
    before = owner_snapshot(settings.ragglass_data_dir)
    output = ROOT / ".data/launch"
    output.mkdir(parents=True, exist_ok=True)
    name = "ragglass-demo-" + uuid.uuid4().hex[:12]
    api_port, qdrant_port = port(), port()
    assert api_port != qdrant_port
    base = f"http://127.0.0.1:{api_port}"
    process, created = None, False
    report = {"mock": False, "api_port": api_port, "qdrant_port": qdrant_port}
    report["application_source_sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in (ROOT / "backend/ragglass", ROOT / "frontend/src")
        for p in folder.iterdir()
        if p.suffix in {".py", ".ts", ".vue", ".css"}
    }
    report["source_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    # The public application permalink must describe the UI/backend actually recorded.
    for path, digest in report["application_source_sha256"].items():
        assert (
            hashlib.sha256(
                subprocess.check_output(
                    ["git", "show", f"{report['source_commit']}:{path}"], cwd=ROOT
                )
            ).hexdigest()
            == digest
        ), f"Uncommitted application source: {path}"
    subprocess.run(["npm", "--prefix", "frontend", "run", "build"], cwd=ROOT, check=True)
    with TemporaryDirectory(prefix="demo-", dir=ROOT / ".data") as temporary:
        with (output / "server.log").open("wb") as log:
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
                )
                created = True
                env = {
                    **os.environ,
                    "RAGGLASS_DATA_DIR": temporary,
                    "QDRANT_URL": f"http://127.0.0.1:{qdrant_port}",
                    "QDRANT_API_KEY": "",
                }
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
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Owned API exited; inspect .data/launch/server.log")
                    try:
                        response = httpx.get(base + "/api/health", timeout=2, trust_env=False)
                        if response.status_code == 200 and response.json()["dependencies"] == {
                            "qdrant": "ready",
                            "llm": "ready",
                        }:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
                else:
                    raise TimeoutError("Owned API/model dependencies did not become ready")
                print(
                    "Recording fresh public PDFs against an owned loopback API/Qdrant.", flush=True
                )
                subprocess.run(
                    ["node", "scripts/capture_demo.mjs"],
                    cwd=ROOT,
                    env={
                        **env,
                        "RAGGLASS_BASE_URL": base,
                        "RAGGLASS_DEMO_CLEANUP": "1",
                    },
                    check=True,
                )
                report["completed"] = True
            finally:
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                if created:
                    subprocess.run(
                        ["docker", "rm", "--force", name], check=True, capture_output=True
                    )
                report["owner_workspace_unchanged"] = before == owner_snapshot(
                    settings.ragglass_data_dir
                )
                report["owned_ports_closed"] = True
                for value in (api_port, qdrant_port):
                    with socket.socket() as s:
                        s.settimeout(1)
                        report["owned_ports_closed"] &= s.connect_ex(("127.0.0.1", value)) != 0
                (output / "service-verification.json").write_text(
                    json.dumps(report, indent=2) + "\n"
                )
                assert report["owner_workspace_unchanged"] and report["owned_ports_closed"]
                print("Owner data unchanged; owned API/Qdrant stopped and removed.", flush=True)


if __name__ == "__main__":
    main()
