"""Synthetic context, recovery and summary contracts; not evidence of model quality."""

import asyncio
import json
import threading
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from ragglass.config import Settings
from ragglass.context import ContextBudget, GenerationOptions
from ragglass.errors import PipelineError
from ragglass.evaluation import aggregate, comparison, score_case
from ragglass.generation import native_usage
from ragglass.llm import Completion, LLMClient, make_prompt
from ragglass.store import Store, now
from ragglass.summary import Notes, summary_prompt
from test_query_jobs import stack, terminal


def answer(cid):
    return json.dumps({"answerable": True, "answer": "30 MB", "citation_ids": [cid]})


def test_budget_counts_full_unicode_prompt_schema_and_output_reservation():
    settings = Settings()
    options = GenerationOptions.defaults(settings)
    budget = ContextBudget(settings, options)
    report = budget.measure(make_prompt("中文 English", []), Completion.model_json_schema())
    assert report["is_estimate"] and report["input_utf8_bytes"] > report["input_characters"]
    assert report["estimated_input_tokens"] > report["input_utf8_bytes"]
    assert report["input_budget_tokens"] == 8192 - 768 - 256 - 256
    assert report["fits"]


def test_budget_keeps_whole_chunks_and_excluded_ids_cannot_be_cited(tmp_path, monkeypatch):
    app, evidence, request = stack(tmp_path, monkeypatch)
    excluded = {**evidence[0], "id": str(uuid.uuid4()), "text": "中" * 4000}
    evidence.append(excluded)
    prompts = []

    async def model(messages, **kwargs):
        prompts.append(messages)
        return answer(excluded["id"]), {"prompt_eval_count": 100, "eval_count": 20}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        result = client.post("/api/query", json=request).json()
        assert result["status"] == "failed" and result["error_code"] == "invalid_citation"
        assert result["context"]["selected_ids"] == [evidence[0]["id"]]
        assert result["context"]["omitted_ids"] == [excluded["id"]]
        assert result["evidence"][1]["text"] == excluded["text"]
        assert len(prompts) == 2  # Initial rejection, one bounded repair, then stop.
        assert excluded["id"] not in json.dumps(prompts)
        assert result["usage"]["reported_input_tokens"] == 200
        assert result["usage"]["reported_calls"] == 2


def test_no_fitting_evidence_fails_before_model_and_preserves_source(tmp_path, monkeypatch):
    app, evidence, request = stack(tmp_path, monkeypatch)
    evidence[0]["text"] = "中" * 5000

    async def unexpected(*args, **kwargs):
        raise AssertionError("Oversized context must not call the model")

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", unexpected)
    with TestClient(app) as client:
        result = client.post("/api/query", json=request).json()
        assert result["error_code"] == "context_budget_exceeded"
        assert result["evidence"] and not result["attempts"]


def test_validation_feedback_repairs_schema_without_reusing_invalid_output(tmp_path, monkeypatch):
    app, evidence, request = stack(tmp_path, monkeypatch)
    prompts = []

    async def model(messages, **kwargs):
        prompts.append(messages)
        return (
            "malformed-untrusted-output" if len(prompts) == 1 else answer(evidence[0]["id"]),
            {"prompt_eval_count": 200, "eval_count": 30},
        )

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        result = client.post("/api/query", json=request).json()
        assert result["status"] == "completed"
        assert result["attempts"][0]["raw_response"] == "malformed-untrusted-output"
        assert result["attempts"][1]["reason"] == "validation_repair"
        assert "invalid_model_response" in prompts[1][-1]["content"]
        assert "malformed-untrusted-output" not in json.dumps(prompts[1])
        assert result["usage"]["reported_output_tokens"] == 60
        assert "attempts" not in client.get("/api/runs").json()[0]
        assert "attempts" not in client.get("/api/runs/catalog").json()["items"][0]


@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (401, False), (404, False)])
def test_http_retry_classification(status, retryable):
    response = httpx.Response(status, request=httpx.Request("POST", "http://fixture.invalid"))
    error = LLMClient._request_error(
        httpx.HTTPStatusError("fixture", request=response.request, response=response)
    )
    assert error.retryable is retryable


def test_transient_retry_then_success_and_missing_usage_is_unknown(tmp_path, monkeypatch):
    app, evidence, request = stack(tmp_path, monkeypatch)
    app.state.pipeline.settings.llm_retry_delay_seconds = 0
    calls = []

    async def model(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            raise PipelineError("llm_http_error", "Synthetic 503", retryable=True)
        return answer(evidence[0]["id"]), {}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        result = client.post("/api/query", json=request).json()
        assert result["status"] == "completed" and len(calls) == 2
        assert calls[0] == calls[1]
        assert result["attempts"][1]["reason"] == "transport_retry"
        assert result["usage"]["unreported_calls"] == 2
        assert result["usage"]["reported_calls"] == 0


def test_persistent_transport_error_stops_at_attempt_limit(tmp_path, monkeypatch):
    app, _, request = stack(tmp_path, monkeypatch)
    app.state.pipeline.settings.llm_retry_delay_seconds = 0

    async def model(*args, **kwargs):
        raise PipelineError("llm_unavailable", "Synthetic outage", retryable=True)

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        result = client.post("/api/query", json=request).json()
        assert result["status"] == "failed" and len(result["attempts"]) == 3
        assert all(a["status"] == "failed" for a in result["attempts"])


def test_cancel_during_backoff_prevents_next_call(tmp_path, monkeypatch):
    app, _, request = stack(tmp_path, monkeypatch)
    app.state.pipeline.settings.llm_retry_delay_seconds = 10
    entered = threading.Event()
    calls = []

    async def model(*args, **kwargs):
        calls.append(1)
        entered.set()
        raise PipelineError("llm_unavailable", "Synthetic outage", retryable=True)

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post("/api/query/start", json=request).json()["id"]
        assert entered.wait(5)
        client.post(f"/api/runs/{rid}/cancel").raise_for_status()
        assert terminal(client, rid)["status"] == "cancelled"
        assert len(calls) == 1


def test_workflow_deadline_stops_waiting_model(tmp_path, monkeypatch):
    app, _, request = stack(tmp_path, monkeypatch)
    app.state.pipeline.settings.workflow_timeout_seconds = 0.05

    async def model(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        result = client.post("/api/query", json=request).json()
        assert result["error_code"] == "workflow_timeout"
        assert result["attempts"][0]["error_code"] == "workflow_timeout"


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_per_run_generation_options_are_forwarded_without_mutating_defaults(provider):
    client = LLMClient(Settings(llm_provider=provider))
    options = GenerationOptions(temperature=0.8, top_p=0.9, max_tokens=512)
    _, payload, _ = client._request([], options, {"type": "object"})
    if provider == "ollama":
        assert payload["options"]["temperature"] == 0.8
        assert payload["options"]["top_p"] == 0.9
        assert payload["options"]["num_predict"] == 512
    else:
        assert payload["temperature"] == 0.8 and payload["top_p"] == 0.9
        assert payload["max_tokens"] == 512
    assert client.snapshot()["temperature"] == 0
    assert client.snapshot()["max_tokens"] == 768


@pytest.mark.parametrize("field,value", [("temperature", -1), ("top_p", 0), ("max_tokens", 1)])
def test_bad_generation_options_are_rejected_before_job_creation(
    tmp_path, monkeypatch, field, value
):
    app, _, request = stack(tmp_path, monkeypatch)
    options = {"temperature": 0, "top_p": 1, "max_tokens": 768, field: value}
    with TestClient(app) as client:
        assert (
            client.post("/api/query/start", json={**request, "generation": options}).status_code
            == 422
        )
        assert not app.state.query_jobs.active and not app.state.store.runs()


def test_unknown_query_summary_and_generation_parameters_are_rejected(tmp_path, monkeypatch):
    app, _, request = stack(tmp_path, monkeypatch)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/query/start", json={**request, "unknown_tool_argument": 1}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/summary/start",
                json={"document_ids": request["document_ids"], "unknown_tool_argument": 1},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/query/start",
                json={
                    **request,
                    "generation": {
                        "temperature": 0,
                        "top_p": 1,
                        "max_tokens": 768,
                        "made_up_parameter": 1,
                    },
                },
            ).status_code
            == 422
        )
        assert not app.state.query_jobs.active and not app.state.store.runs()


def summary_stack(tmp_path, monkeypatch, count=12):
    app, evidence, request = stack(tmp_path, monkeypatch)
    chunks = [
        {**evidence[0], "id": str(uuid.uuid4()), "text": f"Part {i}: " + "x" * 1400}
        for i in range(count)
    ]
    app.state.store.save_chunks(request["document_ids"][0], chunks)
    return app, chunks, request


def test_summary_reads_every_chunk_and_keeps_per_node_citation_scope(tmp_path, monkeypatch):
    app, chunks, request = summary_stack(tmp_path, monkeypatch)
    seen = []

    async def model(messages, **kwargs):
        data = json.loads(messages[1]["content"])["data"]
        seen.extend(cid for item in data for cid in item["citation_ids"])
        notes = [{"text": "Concise synthetic fact", "citation_ids": [data[0]["citation_ids"][0]]}]
        result = (
            {"notes": notes}
            if "notes" in kwargs["schema"]["properties"]
            else {"answerable": True, "points": notes * 3}
        )
        return json.dumps(result), {"prompt_eval_count": 100, "eval_count": 50}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post(
            "/api/summary/start", json={"document_ids": request["document_ids"]}
        ).json()["id"]
        result = terminal(client, rid)
        assert result["status"] == "completed" and result["kind"] == "summary"
        assert len(result["summary_points"]) == 3
        assert set(result["workflow"]["mapped_source_ids"]) == {c["id"] for c in chunks}
        assert set(seen) == {c["id"] for c in chunks}
        assert result["workflow"]["map_batches"] > 1
        for attempt in result["attempts"]:
            assert attempt["context"]["fits"]
        assert result["usage"]["reported_calls"] == len(result["attempts"])
        assert "workflow" not in client.get("/api/runs").json()[0]


def test_summary_rejects_a_chunk_from_a_different_map_batch(tmp_path, monkeypatch):
    app, chunks, request = summary_stack(tmp_path, monkeypatch)

    async def model(*args, **kwargs):
        return json.dumps(
            {"notes": [{"text": "Wrong batch", "citation_ids": [chunks[-1]["id"]]}]}
        ), {}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post(
            "/api/summary/start", json={"document_ids": request["document_ids"]}
        ).json()["id"]
        result = terminal(client, rid)
        assert result["error_code"] == "invalid_citation" and not result["citations"]
        assert result["workflow"]["nodes"][0]["status"] == "failed"
        assert len(result["attempts"]) == 2


def test_hierarchical_summary_reduces_notes_before_final_three_points(tmp_path, monkeypatch):
    app, chunks, request = summary_stack(tmp_path, monkeypatch, count=6)
    app.state.pipeline.settings.llm_context_tokens = 4096
    for i, chunk in enumerate(chunks):
        chunk["text"] = f"Part {i}: " + "x" * 900
    app.state.store.save_chunks(request["document_ids"][0], chunks)

    async def model(messages, **kwargs):
        items = json.loads(messages[1]["content"])["data"]
        note = {"text": "Compact fact", "citation_ids": [items[0]["citation_ids"][0]]}
        if "points" in kwargs["schema"]["properties"]:
            result = {"answerable": True, "points": [note] * 3}
        else:
            result = {
                "notes": [{**note, "text": "x" * 950} for _ in range(3)]
                if items[0]["text"].startswith("Part")
                else [note]
            }
        return json.dumps(result), {}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post(
            "/api/summary/start", json={"document_ids": request["document_ids"]}
        ).json()["id"]
        result = terminal(client, rid)
        assert result["status"] == "completed", result["error"]
        assert any(n["phase"] == "reduce" for n in result["workflow"]["nodes"])
        assert len(result["workflow"]["mapped_source_ids"]) == len(chunks)
        assert len(result["summary_points"]) == 3


def test_summary_cancel_stops_remaining_nodes_and_preserves_completed_map(tmp_path, monkeypatch):
    app, _, request = summary_stack(tmp_path, monkeypatch)
    waiting = threading.Event()
    calls = []

    async def model(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 2:
            waiting.set()
            await asyncio.Event().wait()
        items = json.loads(messages[1]["content"])["data"]
        return json.dumps(
            {"notes": [{"text": "First map", "citation_ids": [items[0]["citation_ids"][0]]}]}
        ), {}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post(
            "/api/summary/start", json={"document_ids": request["document_ids"]}
        ).json()["id"]
        assert waiting.wait(5)
        assert client.delete(f"/api/documents/{request['document_ids'][0]}").status_code == 409
        client.post(f"/api/runs/{rid}/cancel").raise_for_status()
        result = terminal(client, rid)
        assert result["status"] == "cancelled" and len(calls) == 2
        assert result["workflow"]["nodes"][0]["status"] == "completed"
        assert result["workflow"]["nodes"][1]["status"] == "cancelled"
        assert result["answer"] is None and not result["citations"]
        app.state.store.recover_interrupted()
        assert app.state.store.run(rid)["workflow"] == result["workflow"]


def test_summary_call_cap_refuses_partial_source_coverage(tmp_path, monkeypatch):
    app, _, request = summary_stack(tmp_path, monkeypatch)
    app.state.pipeline.settings.workflow_max_calls = 1
    with TestClient(app) as client:
        rid = client.post(
            "/api/summary/start", json={"document_ids": request["document_ids"]}
        ).json()["id"]
        result = terminal(client, rid)
        assert result["error_code"] == "workflow_call_limit" and not result["attempts"]


def test_summary_noncompacting_reduce_stops_instead_of_looping(tmp_path, monkeypatch):
    app, chunks, request = summary_stack(tmp_path, monkeypatch, count=6)
    app.state.pipeline.settings.llm_context_tokens = 4096
    for i, chunk in enumerate(chunks):
        chunk["text"] = f"Part {i}: " + "x" * 900
    app.state.store.save_chunks(request["document_ids"][0], chunks)

    async def model(messages, **kwargs):
        items = json.loads(messages[1]["content"])["data"]
        # Three large notes per node force a reduction and then deliberately resist compaction.
        return json.dumps(
            {"notes": [{"text": "x" * 950, "citation_ids": [items[0]["citation_ids"][0]]}] * 3}
        ), {}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        rid = client.post(
            "/api/summary/start", json={"document_ids": request["document_ids"]}
        ).json()["id"]
        result = terminal(client, rid)
        assert result["status"] == "failed"
        assert result["error_code"] == "summary_not_compacting"
        assert len(result["attempts"]) <= app.state.pipeline.settings.workflow_max_calls


def test_summary_budget_partitions_sources_without_slicing_text():
    settings = Settings()
    budget = ContextBudget(settings, GenerationOptions.defaults(settings))
    items = [{"text": "中文" * 500, "citation_ids": [str(uuid.uuid4())]} for _ in range(5)]
    batches = budget.batches(
        items, lambda batch: summary_prompt(batch, "zh-TW", "map"), Notes.model_json_schema()
    )
    assert [item for batch in batches for item in batch] == items
    assert len(batches) > 1


def test_evaluation_separates_page_recall_text_matching_refusals_and_failures():
    run = {
        "id": "fixture",
        "status": "completed",
        "answerable": False,
        "answer": "Cannot confirm",
        "evidence": [{"pages": [2]}],
        "citations": [],
        "timings_ms": {"total": 20},
    }
    positive = score_case(
        {"id": "p", "answerable": True, "expected_pages": [1, 2], "expected_any": ["30"]}, run
    )
    negative = score_case({"id": "n", "answerable": False}, run)
    failed = score_case({"id": "f", "answerable": False}, {**run, "status": "failed"})
    result = aggregate([positive, negative, failed])
    assert positive["gold_page_recall_at_k"] == 0.5
    assert not positive["expected_text_match"] and positive["gold_page_citation_coverage"] == 0
    assert result["unanswerable_refused"] == 1 and result["answerable_refused"] == 1
    assert result["answerability_matches"] == 1 and result["completed"] == 2


def test_evaluation_comparison_requires_same_annotations_document_and_retrieval():
    previous = {
        "provenance": {"hash": "fixture", "top_k": 5},
        "generation": {"temperature": 0},
        "metrics": {"latency_median_ms": 20},
    }
    current = {**previous, "generation": {"temperature": 0.8}, "metrics": {"latency_median_ms": 25}}
    assert comparison(previous, current)["deltas"]["latency_median_ms"] == 5
    assert not comparison(previous, {**current, "provenance": {"hash": "different"}})["comparable"]


def test_incomplete_or_bad_native_usage_stays_unknown_and_preserves_known_counts(
    tmp_path, monkeypatch
):
    assert native_usage({"usage": "bad", "eval_count": -1}) == (None, None)
    assert native_usage({"usage": {"prompt_tokens": 50}}) == (50, None)
    app, evidence, request = stack(tmp_path, monkeypatch)

    async def model(*args, **kwargs):
        return answer(evidence[0]["id"]), {"usage": {"prompt_tokens": 50}}

    monkeypatch.setattr(app.state.pipeline.llm, "generate_async", model)
    with TestClient(app) as client:
        run = client.post("/api/query", json=request).json()
        assert run["status"] == "completed"
        assert run["usage"]["reported_input_tokens"] == 50
        assert run["usage"]["reported_calls"] == 0 and run["usage"]["unreported_calls"] == 1


def test_crash_recovery_marks_pending_nodes_attempts_and_unknown_usage(tmp_path):
    store = Store(tmp_path)
    store.save_run(
        {
            "id": "interrupted",
            "created_at": now(),
            "status": "running",
            "prompt": ["preserved"],
            "attempts": [{"status": "running", "context": {}}],
            "workflow": {"nodes": [{"status": "completed"}, {"status": "running"}]},
            "usage": {"unreported_calls": 0},
        }
    )
    store.recover_interrupted()
    recovered = store.run("interrupted")
    assert recovered["error_code"] == "interrupted" and recovered["stage"] == "failed"
    assert recovered["attempts"][0]["status"] == "failed"
    assert recovered["workflow"]["nodes"][0]["status"] == "completed"
    assert recovered["workflow"]["nodes"][1]["error_code"] == "interrupted"
    assert recovered["usage"]["unreported_calls"] == 1 and recovered["prompt"] == ["preserved"]
    store.recover_interrupted()
    assert store.run("interrupted") == recovered
