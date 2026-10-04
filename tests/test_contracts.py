import asyncio
import json
import uuid

import httpx
import pytest
from ragglass.config import Settings
from ragglass.errors import PipelineError
from ragglass.llm import LLMClient, validate_completion
from ragglass.store import Store, now


def evidence():
    return [
        {
            "id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "document_hash": "abc",
            "filename": "sample.pdf",
            "page": 2,
            "pages": [2],
            "text": "Maximum upload: 30 MB",
            "provenance": [],
            "coordinates_available": False,
            "coordinate_scope": "unavailable",
        }
    ]


def test_citation_maps_exact_retrieved_id_to_document_and_page():
    chunks = evidence()
    response = json.dumps(
        {"answerable": True, "answer": "30 MB", "citation_ids": [chunks[0]["id"]]}
    )
    result = validate_completion(response, chunks)
    assert result["citations"][0]["document_id"] == chunks[0]["document_id"]
    assert result["citations"][0]["page"] == 2
    assert result["citations"][0]["coordinates_available"] is False


def test_citation_outside_current_retrieval_is_rejected():
    raw = json.dumps({"answerable": True, "answer": "30 MB", "citation_ids": [str(uuid.uuid4())]})
    with pytest.raises(PipelineError, match="本次未檢索"):
        validate_completion(raw, evidence())


def test_uncited_claim_becomes_insufficient_evidence():
    result = validate_completion(
        json.dumps({"answerable": True, "answer": "Electricity costs $1,000.", "citation_ids": []}),
        evidence(),
    )
    assert result["answerable"] is False
    assert result["citations"] == []
    assert "cannot be confirmed" in result["answer"]


def test_malformed_model_json_is_actionable():
    with pytest.raises(PipelineError) as exc:
        validate_completion("not JSON", evidence())
    assert exc.value.code == "invalid_model_response"


def test_real_connection_refusal_has_actionable_model_error():
    # Real TCP failure, not a mocked/precomputed model response.
    client = LLMClient(Settings(llm_base_url="http://127.0.0.1:1", llm_timeout_seconds=1))
    with pytest.raises(PipelineError) as exc:
        client.generate([{"role": "user", "content": "Hello"}])
    assert exc.value.code == "llm_unavailable"
    assert "LLM_BASE_URL" in exc.value.message


def test_sqlite_persists_document_and_run_across_instances(tmp_path):
    store = Store(tmp_path)
    doc = {"id": "d1", "hash": "h1", "status": "ready"}
    run = {"id": "r1", "created_at": now(), "status": "completed", "prompt": ["original prompt"]}
    store.save_document(doc)
    store.save_run(run)
    reopened = Store(tmp_path)
    assert reopened.document("d1") == doc
    assert reopened.run("r1")["prompt"] == run["prompt"]


def test_restart_marks_interrupted_work_failed(tmp_path):
    store = Store(tmp_path)
    store.save_document({"id": "d1", "hash": "h1", "status": "embedding"})
    store.save_run({"id": "r1", "created_at": now(), "status": "running", "prompt": ["kept"]})
    Store(tmp_path).recover_interrupted()
    assert store.document("d1")["status"] == "failed"
    assert store.run("r1")["status"] == "failed"
    assert store.run("r1")["prompt"] == ["kept"]


def test_secrets_are_excluded_from_recorded_settings():
    client = LLMClient(Settings(llm_api_key="private-test-key"))
    assert "private-test-key" not in json.dumps(client.snapshot())


def test_openai_compatible_wire_format(monkeypatch):
    # Explicit synthetic HTTP contract fixture, not live model inference.
    requests = []

    def responder(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "fixture-model",
                "usage": {"completion_tokens": 10},
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answerable": False,
                                    "answer": "Cannot confirm.",
                                    "citation_ids": [],
                                }
                            )
                        }
                    }
                ],
            },
        )

    original_client = httpx.Client
    transport = httpx.MockTransport(responder)
    monkeypatch.setattr(httpx, "Client", lambda **kw: original_client(transport=transport, **kw))
    client = LLMClient(
        Settings(
            llm_provider="openai",
            llm_base_url="http://fixture.invalid/v1",
            llm_model="fixture-model",
            llm_api_key="fixture-key",
        )
    )
    raw, metrics = client.generate([{"role": "user", "content": "Question"}])
    assert str(requests[0].url) == "http://fixture.invalid/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer fixture-key"
    assert json.loads(requests[0].content)["response_format"] == {"type": "json_object"}
    assert metrics["model"] == "fixture-model"
    assert validate_completion(raw, [])["answerable"] is False


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_async_model_adapter_uses_same_json_contract(provider, monkeypatch):
    # Explicit synthetic wire-format fixture; no live model inference.
    requests = []
    content = json.dumps({"answerable": False, "answer": "Cannot confirm.", "citation_ids": []})

    def responder(request):
        requests.append(request)
        body = (
            {"model": "fixture", "message": {"content": content}, "eval_count": 4}
            if provider == "ollama"
            else {"model": "fixture", "choices": [{"message": {"content": content}}]}
        )
        return httpx.Response(200, json=body)

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_client(transport=httpx.MockTransport(responder), **kw),
    )
    client = LLMClient(
        Settings(llm_provider=provider, llm_base_url="http://fixture.invalid", llm_model="fixture")
    )
    raw, metrics = asyncio.run(client.generate_async([{"role": "user", "content": "Question"}]))
    payload = json.loads(requests[0].content)
    assert metrics["model"] == "fixture" and raw == content
    if provider == "ollama":
        assert requests[0].url.path == "/api/chat"
        assert payload["stream"] is False and payload["format"]["type"] == "object"
    else:
        assert requests[0].url.path == "/chat/completions"
        assert payload["response_format"] == {"type": "json_object"}
