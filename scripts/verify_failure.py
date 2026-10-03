"""Verify failed generation against real E5/Qdrant; never stop the shared model service."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ragglass.config import Settings  # noqa: E402
from ragglass.main import create_app  # noqa: E402


def main():
    with httpx.Client(trust_env=False) as client:
        docs = client.get("http://127.0.0.1:8000/api/documents").json()
    sample = next(d for d in docs if d["filename"] == "ragglass-field-guide.pdf")
    with TemporaryDirectory(prefix="ragglass-failure-") as folder:
        app = create_app(
            Settings(
                ragglass_data_dir=Path(folder),
                llm_base_url="http://127.0.0.1:1",
                llm_timeout_seconds=1,
            )
        )
        app.state.store.save_document(sample)
        with TestClient(app) as client:
            response = client.post(
                "/api/query",
                json={
                    "question": "What is the maximum upload size for the Cedar pilot?",
                    "document_ids": [sample["id"]],
                    "top_k": 5,
                    "score_threshold": 0.70,
                },
            )
            assert response.status_code == 200
            run = response.json()
            assert run["status"] == "failed" and run["error_code"] == "llm_unavailable"
            assert run["evidence"] and run["prompt"]
            assert not run["citations"] and run["answer"] is None
            assert "LLM_BASE_URL" in run["error"]
            assert client.get(f"/api/runs/{run['id']}").json() == run
            (ROOT / ".data" / "failure-verification.json").write_text(
                json.dumps(run, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print("PASS real retrieval + unreachable LLM: actionable error and saved evidence")


if __name__ == "__main__":
    main()
