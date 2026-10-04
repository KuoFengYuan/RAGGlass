"""Run annotated bilingual sample questions against an already running local workbench."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ragglass.evaluation import aggregate, comparison, score_case  # noqa: E402
from ragglass.store import now  # noqa: E402


def evaluate(client, document_id, dataset, generation=None, top_k=5, threshold=0.7):
    response = client.get(f"documents/{document_id}")
    response.raise_for_status()
    doc = response.json()
    if doc["status"] != "ready" or doc["hash"] != dataset["document_sha256"]:
        raise ValueError("Evaluation requires the indexed PDF named by the dataset hash")
    runs, scores = [], []
    for case in dataset["cases"]:
        response = client.post(
            "query",
            json={
                "question": case["question"],
                "document_ids": [document_id],
                "top_k": top_k,
                "score_threshold": threshold,
                "generation": generation,
            },
        )
        response.raise_for_status()
        run = response.json()
        runs.append(run)
        scores.append(score_case(case, run))
        print(f"{case['id']}: {run['status']} {run['timings_ms']['total']} ms", flush=True)
    return {
        "checked_at": now(),
        "fixture": "fictional CC0 sample; this is a smoke dataset, not production accuracy",
        "provenance": {
            "dataset_sha256": hashlib.sha256(
                json.dumps(dataset, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest(),
            "document_sha256": doc["hash"],
            "parser": doc["parser"],
            "chunking": doc["chunking"],
            "embedding": doc["embedding"],
            "retrieval": runs[0]["settings"]["retrieval"],
            "prompt_version": runs[0]["settings"]["prompt_version"],
        },
        "generation": runs[0]["settings"]["llm"],
        "metrics": aggregate(scores),
        "scores": scores,
        "runs": runs,
        "limitations": [
            "Gold-page recall is not chunk recall or semantic entailment",
            "Expected-text matching is a literal heuristic, not a factuality judge",
            "Native token usage may be missing for failed calls",
            "Latency is sequential wall time including retries; shared workload effects remain",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "examples/evaluation-cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / ".data/evaluation.json")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-p", type=float)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.7)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Use a loopback workbench URL (or an SSH tunnel)")
    dataset = json.loads(args.dataset.read_text())
    with httpx.Client(
        base_url=args.base_url.rstrip("/") + "/api/", timeout=660, trust_env=False
    ) as client:
        config = client.get("config")
        config.raise_for_status()
        defaults = config.json()["llm"]
        generation = {
            key: getattr(args, key) if getattr(args, key) is not None else defaults[key]
            for key in ("temperature", "top_p", "max_tokens")
        }
        report = evaluate(client, args.document_id, dataset, generation, args.top_k, args.threshold)
    if args.compare:
        report["comparison"] = comparison(json.loads(args.compare.read_text()), report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["metrics"], indent=2), flush=True)
    print(f"Report saved to {args.output}", flush=True)


if __name__ == "__main__":
    main()
