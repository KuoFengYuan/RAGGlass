"""Real retrieval checks inside verify_usability's disposable API/Qdrant workspace."""

import json
import time
import unicodedata

from evaluate import evaluate
from ragglass.evaluation import comparison


def check_retrieval(client, doc, report, checked, root):
    measured = {"evaluations": {}}
    report["retrieval"] = measured
    # Record the original dense baseline before running any new retrieval treatment.
    legacy = evaluate(
        client, doc["id"], json.loads((root / "examples/evaluation-cases.json").read_text())
    )
    assert legacy["metrics"]["completed"] == 12
    measured["legacy_dense"] = legacy
    checked("original 12-case dense baseline recorded with real embeddings/inference")
    fixture = root / "examples/ragglass-retrieval-lab.pdf"
    with fixture.open("rb") as file:
        response = client.post("documents", files={"file": (fixture.name, file, "application/pdf")})
    response.raise_for_status()
    lab = response.json()
    deadline = time.monotonic() + 600
    while lab["status"] not in {"ready", "failed"}:
        if time.monotonic() > deadline:
            raise TimeoutError("Retrieval lab ingestion exceeded 600 seconds")
        time.sleep(0.2)
        lab = client.get(f"documents/{lab['id']}").json()
    assert lab["status"] == "ready", lab.get("error")
    assert lab["page_count"] == 8
    chunks = client.get(f"documents/{lab['id']}/chunks").json()
    measured["document"] = lab
    assert any(
        6 in chunk["pages"] and "九十天" in unicodedata.normalize("NFKC", chunk["text"])
        for chunk in chunks
    )
    checked(f"real eight-page English/Chinese Docling/E5 lab: {lab['chunk_count']} chunks")
    dataset = json.loads((root / "examples/retrieval-cases.json").read_text())
    for mode in ("dense", "keyword", "hybrid"):
        result = evaluate(client, lab["id"], dataset, top_k=3, retrieval_mode=mode)
        assert result["metrics"]["completed"] == 16
        for run in result["runs"]:
            assert run["retrieval_trace"]["complete"]
            assert len(run["evidence"]) <= 3
            assert all(
                c["id"] in run.get("context", {}).get("selected_ids", []) for c in run["citations"]
            )
            assert all(e["document_id"] == lab["id"] for e in run["evidence"])
            assert all(
                e["score_kind"] == {"dense": "cosine", "keyword": "bm25", "hybrid": "rrf"}[mode]
                for e in run["evidence"]
            )
            if mode == "keyword":
                assert "embedding" not in run["timings_ms"] and not run["retrieval_trace"]["dense"]
            if mode == "hybrid":
                assert all(
                    len(run["retrieval_trace"][branch]) <= 20 for branch in ("dense", "keyword")
                )
        if mode != "dense":
            result["comparison"] = comparison(measured["evaluations"]["dense"], result, "retrieval")
            assert result["comparison"]["comparable"]
        measured["evaluations"][mode] = result
        (root / f".data/retrieval-evaluation-{mode}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
        checked(f"16-case live {mode} evaluation: {json.dumps(result['metrics'])}")
    request = {
        "document_ids": [lab["id"]],
        "question": "What does E-4097 mean for CEDAR-X17?",
        "retrieval_mode": "hybrid",
        "top_k": 3,
        "score_threshold": 1,
    }
    response = client.post("query", json=request)
    response.raise_for_status()
    run = response.json()
    assert run["status"] == "completed" and run["answerable"]
    assert not run["retrieval_trace"]["dense"] and run["retrieval_trace"]["keyword"]
    assert run["evidence"] and all("dense" not in e["retrieval_scores"] for e in run["evidence"])
    measured["threshold_scope"] = run
    checked("live cosine=1 threshold does not filter BM25 or RRF evidence")
    response = client.post(
        "query",
        json={**request, "retrieval_mode": "keyword", "question": "zzq881nonesuch"},
    )
    response.raise_for_status()
    empty = response.json()
    assert empty["status"] == "completed" and not empty["evidence"] and not empty["citations"]
    assert not empty["attempts"]
    measured["empty_keyword"] = empty
    checked("unknown keyword refuses before inference without fabricated citations")


if __name__ == "__main__":
    from verify_usability import main

    main(browser=True, retrieval=True)
