"""Synthetic ranking/citation/lifecycle contracts, not evidence of model quality."""

import copy
import json
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from ragglass.errors import PipelineError
from ragglass.evaluation import comparison, score_case
from ragglass.keyword import KeywordRetriever, tokenize
from ragglass.retrieval import rank_evidence, snapshot
from ragglass.store import Store
from test_query_jobs import stack, terminal


def test_keyword_normalizes_width_case_identifier_parts_and_chinese():
    terms = tokenize("ＣＥＤＡＲ‑Ｘ１７ 文件庫查詢 E-4097")
    assert {"cedar-x17", "cedar", "x17", "e-4097", "4097", "文件", "件庫", "查詢"} <= set(terms)
    assert "x" not in terms and "17" not in terms
    assert tokenize("the WHAT and") == []
    assert tokenize("⽂件庫九⼗天") == tokenize("文件庫九十天")


def test_bm25_exact_identifiers_length_normalization_ties_and_no_match():
    retriever = KeywordRetriever()
    chunks = [
        {"id": "b", "text": "CEDAR-X17 E-4097 checksum"},
        {"id": "a", "text": "CEDAR-X17 E-4097 checksum"},
        {"id": "c", "text": "CEDAR-X71 E-4079 temperature " + "extra " * 30},
    ]
    results, stats = retriever.search("CEDAR-X17 E-4097", chunks, 2)
    assert [r["id"] for r in results] == ["a", "b"]
    assert results[0]["score"] > 0 and results[0]["rank"] == 1
    assert "cedar-x17" in results[0]["matched_terms"] and stats["corpus_chunks"] == 3
    assert retriever.search("nonexistent-identifier", chunks, 10)[0] == []
    assert retriever.search("", [], 10)[0] == []


def test_rrf_deduplicates_retains_raw_scores_and_deterministic_fused_ranks():
    dense = [{"id": "b", "rank": 1, "score": 0.99}, {"id": "a", "rank": 2, "score": 0.71}]
    keyword = [
        {"id": "a", "rank": 1, "score": 300, "matched_terms": ["exact"]},
        {"id": "c", "rank": 2, "score": 1000, "matched_terms": ["word"]},
    ]
    result = rank_evidence(dense, keyword, "hybrid", 2)
    assert [r["id"] for r in result] == ["a", "b"]
    assert result[0]["score"] == pytest.approx(1 / 61 + 1 / 62)
    assert result[0]["score_kind"] == "rrf" and result[0]["rank"] == 1
    assert result[0]["retrieval_scores"]["dense"] == {"rank": 2, "score": 0.71}
    assert result[0]["retrieval_scores"]["keyword"] == {"rank": 1, "score": 300}
    assert dense[1]["score"] == 0.71  # Inputs are immutable.
    tie = rank_evidence(dense[:1], [{**keyword[0], "id": "a"}], "hybrid", 2)
    assert [r["id"] for r in tie] == ["a", "b"]


def test_keyword_uses_only_selected_stored_chunks_and_tracks_reindex_delete_restart(
    tmp_path, monkeypatch
):
    app, chunks, request = stack(tmp_path, monkeypatch)
    pipeline = app.state.pipeline
    did = request["document_ids"][0]
    pipeline.store.save_chunks(did, chunks)
    other = {**pipeline.store.document(did), "id": str(uuid.uuid4()), "hash": "other"}
    pipeline.store.save_document(other)
    pipeline.store.save_chunks(
        other["id"],
        [
            {
                **chunks[0],
                "id": str(uuid.uuid4()),
                "document_id": other["id"],
                "text": "Maximum upload is 999 MB",
            }
        ],
    )
    monkeypatch.setattr(
        pipeline.embedder, "encode", lambda *a, **kw: pytest.fail("Keyword must skip embedding")
    )
    monkeypatch.setattr(
        pipeline.index, "search", lambda *a: pytest.fail("Keyword must skip Qdrant search")
    )

    async def model(messages, **kwargs):
        return json.dumps(
            {"answerable": True, "answer": "30 MB", "citation_ids": [chunks[0]["id"]]}
        ), {}

    monkeypatch.setattr(pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        run = client.post(
            "/api/query", json={**request, "retrieval_mode": "keyword", "score_threshold": 1}
        ).json()
        assert run["status"] == "completed" and run["citations"][0]["document_id"] == did
        assert run["evidence"][0]["score_kind"] == "bm25"
        assert run["retrieval_trace"]["keyword_corpus"]["corpus_chunks"] == 1
        assert "embedding" not in run["timings_ms"]
        assert Store(tmp_path).run(run["id"])["retrieval_trace"] == run["retrieval_trace"]
        assert "retrieval_trace" not in client.get("/api/runs/catalog").json()["items"][0]
        pipeline.store.save_chunks(did, [{**chunks[0], "text": "replacement-only"}])
        empty = client.post("/api/query", json={**request, "retrieval_mode": "keyword"}).json()
        assert empty["status"] == "completed" and not empty["evidence"] and not empty["citations"]
        pipeline.store.delete_document(did)
        assert pipeline.store.chunks(did) == []


def test_equal_rrf_scores_use_keyword_strength_then_dense_rank_before_arbitrary_ids():
    dense = [
        {"id": "z", "rank": 1, "score": 0.9},
        {"id": "a", "rank": 2, "score": 0.8},
    ]
    keyword = [
        {"id": "a", "rank": 1, "score": 12, "matched_terms": ["shared"]},
        {"id": "z", "rank": 2, "score": 12, "matched_terms": ["shared"]},
    ]
    tied = rank_evidence(dense, keyword, "hybrid", 2)
    assert tied[0]["score"] == tied[1]["score"]
    assert [r["id"] for r in tied] == ["z", "a"]  # Semantic order wins a BM25 tie.
    stronger = rank_evidence(dense, [{**keyword[0], "score": 13}, keyword[1]], "hybrid", 2)
    assert stronger[0]["score"] == stronger[1]["score"]
    assert [r["id"] for r in stronger] == ["a", "z"]


def test_hybrid_overfetches_but_only_final_context_ids_can_be_cited(tmp_path, monkeypatch):
    app, chunks, request = stack(tmp_path, monkeypatch)
    pipeline = app.state.pipeline
    chunks.append(
        {
            **chunks[0],
            "id": str(uuid.uuid4()),
            "rank": 2,
            "score": 0.75,
            "text": "Irrelevant replacement record.",
        }
    )
    pipeline.store.save_chunks(request["document_ids"][0], chunks)
    calls = []
    monkeypatch.setattr(
        pipeline.index,
        "search",
        lambda vector, ids, k, threshold: calls.append((k, threshold)) or chunks,
    )

    async def model(*args, **kwargs):
        return json.dumps(
            {"answerable": True, "answer": "30 MB", "citation_ids": [chunks[1]["id"]]}
        ), {}

    monkeypatch.setattr(pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        run = client.post(
            "/api/query",
            json={**request, "retrieval_mode": "hybrid", "top_k": 1, "candidate_k": 20},
        ).json()
        assert calls == [(20, 0.7)] and run["error_code"] == "invalid_citation"
        assert len(run["retrieval_trace"]["dense"]) == 2 and len(run["evidence"]) == 1
        assert run["evidence"][0]["id"] == chunks[0]["id"]
        assert run["retrieval_trace"]["complete"]
        assert chunks[1]["id"] not in json.dumps(run["prompt"])


def test_hybrid_cancel_keeps_completed_branch_marks_partial_and_skips_model(tmp_path, monkeypatch):
    app, chunks, request = stack(tmp_path, monkeypatch)
    pipeline = app.state.pipeline
    entered, release = threading.Event(), threading.Event()

    def slow(*args):
        entered.set()
        assert release.wait(5)
        return chunks

    monkeypatch.setattr(pipeline.index, "search", slow)
    monkeypatch.setattr(
        pipeline.keyword, "search", lambda *a: pytest.fail("No second branch after stop")
    )
    with TestClient(app) as client:
        try:
            rid = client.post(
                "/api/query/start", json={**request, "retrieval_mode": "hybrid"}
            ).json()["id"]
            assert entered.wait(5)
            client.post(f"/api/runs/{rid}/cancel").raise_for_status()
        finally:
            release.set()
        run = terminal(client, rid)
        assert run["status"] == "cancelled" and run["evidence"]
        assert not run["retrieval_trace"]["complete"] and not run["citations"]
        assert run["retrieval_trace"]["dense"] and not run["retrieval_trace"]["keyword"]


def test_hybrid_does_not_silently_fallback_when_qdrant_fails(tmp_path, monkeypatch):
    app, chunks, request = stack(tmp_path, monkeypatch)
    app.state.store.save_chunks(request["document_ids"][0], chunks)

    def failure(*args):
        raise PipelineError("qdrant_unavailable", "Synthetic failure")

    monkeypatch.setattr(app.state.pipeline.index, "search", failure)
    with TestClient(app) as client:
        run = client.post("/api/query", json={**request, "retrieval_mode": "hybrid"}).json()
        assert run["status"] == "failed" and run["error_code"] == "qdrant_unavailable"
        assert not run["evidence"] and not run["retrieval_trace"]["complete"]


@pytest.mark.parametrize(
    "extra",
    [
        {"retrieval_mode": "invalid"},
        {"candidate_k": 101},
        {"candidate_k": 1, "top_k": 5, "retrieval_mode": "hybrid"},
        {"candidate_k": 0},
    ],
)
def test_retrieval_request_rejects_invalid_modes_and_candidate_limits(tmp_path, extra):
    from ragglass.config import Settings
    from ragglass.main import create_app

    with TestClient(create_app(Settings(ragglass_data_dir=tmp_path))) as client:
        assert (
            client.post(
                "/api/query", json={"question": "q", "document_ids": ["missing"], **extra}
            ).status_code
            == 422
        )


def test_retrieval_comparison_allows_only_mode_as_declared_treatment():
    before = {
        "provenance": {
            "dataset_sha256": "annotations",
            "document_sha256": "pdf",
            "stored_chunks_sha256": "same-chunks",
            "context": {"safety_margin_tokens": 256},
            "resilience": {"max_attempts_per_node": 3},
            "retrieval": snapshot("dense", 3, 0.7, 20, "c"),
        },
        "generation": {"model": "same", "temperature": 0},
        "metrics": {"completed": 16},
    }
    after = copy.deepcopy(before)
    after["provenance"]["retrieval"] = snapshot("hybrid", 3, 0.7, 20, "c")
    assert comparison(before, after, "retrieval")["comparable"]
    assert not comparison(before, after)["comparable"]
    for key, value in (
        ("top_k", 5),
        ("candidate_k", 30),
        ("score_threshold", 0.6),
        ("collection", "other"),
        ("keyword", {}),
    ):
        changed = copy.deepcopy(after)
        changed["provenance"]["retrieval"][key] = value
        assert not comparison(before, changed, "retrieval")["comparable"]
    changed = {**after, "generation": {"model": "same", "temperature": 0.8}}
    assert not comparison(before, changed, "retrieval")["comparable"]
    changed = copy.deepcopy(after)
    changed["provenance"]["dataset_sha256"] = "different-annotations"
    assert not comparison(before, changed, "retrieval")["comparable"]
    for key, value in (
        ("stored_chunks_sha256", "changed-parse"),
        ("context", {"safety_margin_tokens": 1024}),
        ("resilience", {"max_attempts_per_node": 1}),
    ):
        changed = copy.deepcopy(after)
        changed["provenance"][key] = value
        assert not comparison(before, changed, "retrieval")["comparable"]


def test_page_mrr_uses_first_gold_page_rank_and_zero_for_missing_gold():
    run = {
        "id": "synthetic",
        "status": "completed",
        "answerable": False,
        "answer": "",
        "evidence": [{"pages": [1]}, {"pages": [3]}],
        "citations": [],
        "timings_ms": {"total": 10},
    }
    assert (
        score_case({"id": "p", "answerable": True, "expected_pages": [3]}, run)[
            "gold_page_mrr_at_k"
        ]
        == 0.5
    )
    assert (
        score_case({"id": "p", "answerable": True, "expected_pages": [2]}, run)[
            "gold_page_mrr_at_k"
        ]
        == 0
    )
    assert score_case({"id": "n", "answerable": False}, run)["gold_page_mrr_at_k"] is None
