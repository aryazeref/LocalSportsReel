"""Story provider contracts and safe fallbacks, without live API requests."""

import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agent import create_story, find_moment
from app.models import DraftText
from app.services import story_llm


REAL_HTTP_CLIENT = httpx.Client
MOMENT_ID = "oulu-001"
FACT_ID = "oulu-001-1"


def draft(**changes):
    result = {
        "headline": "A fictional Oulu winner",
        "narration": "Aino Virtanen scored for the fictional Oulu Comets.",
        "used_fact_ids": [FACT_ID],
    }
    return {**result, **changes}


def gemini_payload(value=None, *, finish="STOP", parts=None):
    return {"candidates": [{
        "finishReason": finish,
        "content": {"parts": parts if parts is not None else [{
            "text": json.dumps(value if value is not None else draft()),
        }]},
    }]}


@pytest.fixture(autouse=True)
def isolate_llm_configuration(monkeypatch):
    for name in ("LLM_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL", "OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)

    def reject_network(request):
        pytest.fail(f"Unexpected provider request to {request.url.host}")

    monkeypatch.setattr(
        story_llm.httpx, "Client",
        lambda **kwargs: REAL_HTTP_CLIENT(transport=httpx.MockTransport(reject_network), **kwargs),
    )


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-not-a-secret")

    def configure(payload=None, *, status=200, handler=None):
        calls = []

        def respond(request):
            calls.append(request)
            return handler(request) if handler else httpx.Response(status, json=payload)

        monkeypatch.setattr(
            story_llm.httpx, "Client",
            lambda **kwargs: REAL_HTTP_CLIENT(transport=httpx.MockTransport(respond), **kwargs),
        )
        return calls

    return configure


def test_gemini_draft_uses_native_api_and_preserves_review_and_evidence(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    calls = gemini(gemini_payload())

    result = create_story(MOMENT_ID)

    assert result.mode == "llm_draft"
    assert result.publication_status == "review_required"
    assert result.headline == draft()["headline"]
    assert result.narration == draft()["narration"]
    assert [fact.id for fact in result.evidence] == [FACT_ID]
    assert "synthetic" in result.disclaimer
    assert len(calls) == 1
    request = calls[0]
    assert request.method == "POST"
    assert request.url.host == "generativelanguage.googleapis.com"
    assert request.url.path == "/v1beta/models/gemini-test-model:generateContent"
    assert request.headers["x-goog-api-key"] == "test-gemini-key-not-a-secret"
    assert not request.url.query
    body = json.loads(request.content)
    assert "synthetic" in body["systemInstruction"]["parts"][0]["text"]
    prompt = body["contents"][0]["parts"][0]["text"]
    assert MOMENT_ID in prompt and FACT_ID in prompt
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    schema = body["generationConfig"]["responseSchema"]
    assert set(schema["required"]) == {"headline", "narration", "used_fact_ids"}


@pytest.mark.parametrize("case", [
    "quota", "server", "timeout", "invalid_response_json", "no_candidates",
    "blocked", "truncated", "no_content", "invalid_draft_json", "invalid_draft_schema",
])
def test_gemini_failures_fall_back_to_template_without_changing_evidence(gemini, case):
    def handler(request):
        if case == "quota":
            return httpx.Response(429, json={"error": {"message": "test quota reached"}})
        if case == "server":
            return httpx.Response(503, json={"error": {"message": "test unavailable"}})
        if case == "timeout":
            raise httpx.ReadTimeout("test timeout", request=request)
        if case == "invalid_response_json":
            return httpx.Response(200, text="not JSON")
        if case == "no_candidates":
            payload = {"candidates": []}
        elif case == "blocked":
            payload = gemini_payload(finish="SAFETY")
        elif case == "truncated":
            payload = gemini_payload(finish="MAX_TOKENS")
        elif case == "no_content":
            payload = {"candidates": [{"finishReason": "STOP"}]}
        elif case == "invalid_draft_json":
            payload = gemini_payload(parts=[{"text": "not a draft JSON object"}])
        else:
            payload = gemini_payload({"headline": "Missing required fields"})
        return httpx.Response(200, json=payload)

    calls = gemini(handler=handler)
    result = create_story(MOMENT_ID)

    assert result.mode == "template"
    assert result.publication_status == "demo_only"
    assert [fact.id for fact in result.evidence] == [fact.id for fact in find_moment(MOMENT_ID).facts]
    assert len(calls) == 1


@pytest.mark.parametrize("changes", [
    {"used_fact_ids": ["invented-fact"]},
    {"used_fact_ids": []},
    {"headline": "   "},
    {"narration": "   "},
])
def test_unusable_generated_content_falls_back(gemini, changes):
    gemini(gemini_payload(draft(**changes)))
    assert create_story(MOMENT_ID).mode == "template"


def test_gemini_thought_parts_are_not_parsed_as_final_draft(gemini):
    text = json.dumps(draft())
    gemini(gemini_payload(parts=[
        {"thought": True, "text": "Internal thinking is not the draft."},
        {"text": text[:20]},
        {"text": text[20:]},
    ]))
    assert create_story(MOMENT_ID).mode == "llm_draft"


@pytest.mark.parametrize("provider", ["template", "gemini", "openai", "unknown"])
def test_unconfigured_or_disabled_provider_uses_template_without_requests(monkeypatch, provider):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    if provider == "template":
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-not-a-secret")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-not-a-secret")
    assert create_story(MOMENT_ID).mode == "template"


def test_gemini_without_key_does_not_use_existing_openai_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-not-a-secret")

    def reject_openai(**kwargs):
        pytest.fail("Gemini selection must never construct an OpenAI client")

    monkeypatch.setattr(openai, "OpenAI", reject_openai)
    assert create_story(MOMENT_ID).mode == "template"


def test_gemini_failure_does_not_retry_with_openai(gemini, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-not-a-secret")
    gemini({"error": {"message": "test quota reached"}}, status=429)

    def reject_openai(**kwargs):
        pytest.fail("Gemini failure must not trigger another provider")

    monkeypatch.setattr(openai, "OpenAI", reject_openai)
    assert create_story(MOMENT_ID).mode == "template"


def test_invalid_model_cannot_change_gemini_destination(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "other-host/../../model")
    calls = gemini(gemini_payload())
    assert create_story(MOMENT_ID).mode == "template"
    assert calls == []


def test_existing_openai_configuration_still_generates_a_valid_draft(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-not-a-secret")
    monkeypatch.setenv("OPENAI_MODEL", "test-openai-model")
    calls = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(parse=self.parse)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def parse(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_parsed=DraftText(**draft()))

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    result = create_story(MOMENT_ID)
    assert result.mode == "llm_draft"
    assert result.publication_status == "review_required"
    assert len(calls) == 1
    assert calls[0]["model"] == "test-openai-model"
    assert calls[0]["text_format"] is DraftText
