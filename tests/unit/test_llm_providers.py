from __future__ import annotations

import logging

import httpx
import pytest

from incident_agent.llm.base import LLMProviderError, LLMRateLimitError, LLMResponseFormatError
from incident_agent.llm.factory import LLMConfig, create_provider
from incident_agent.llm.mock import MockLLMProvider
from incident_agent.llm.openai_provider import OpenAIProvider
from incident_agent.schemas.llm import LLMCompletionRequest, LLMStructuredReportRequest


def test_mock_provider_supports_plain_and_structured_calls() -> None:
    provider = MockLLMProvider()

    completion = provider.complete(
        LLMCompletionRequest(prompt="hello", model="mock-model", max_output_tokens=20)
    )
    structured = provider.generate_structured_report(
        LLMStructuredReportRequest(prompt="incident", model="mock-model")
    )

    assert completion.content.startswith("Mock completion")
    assert "incident_summary" in structured.content


def test_factory_creates_mock_provider() -> None:
    provider = create_provider(LLMConfig(provider="mock"))
    assert isinstance(provider, MockLLMProvider)


def test_openai_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INCIDENT_AGENT_OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMProviderError):
        OpenAIProvider()


def test_openai_provider_retries_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("INCIDENT_AGENT_OPENAI_API_KEY", "test-key")
    responses = [
        httpx.Response(status_code=429, json={"error": {"message": "rate limited"}}),
        httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"A","severity":"high","impacted_service":"svc",'
                                '"incident_summary":"x","likely_root_causes":[],'
                                '"recommended_actions":[],"evidence":[]}'
                            )
                        }
                    }
                ]
            },
        ),
    ]

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return responses.pop(0)

    monkeypatch.setattr("incident_agent.llm.openai_provider.httpx.Client", FakeClient)
    provider = OpenAIProvider(max_retries=2, retry_backoff_seconds=0.0)
    caplog.set_level(logging.INFO)
    report = provider.generate_incident_report("prompt", model="gpt-4.1-mini")
    assert report.title == "A"
    events = [getattr(record, "event", None) for record in caplog.records]
    assert "provider.request.retry" in events
    assert "provider.request.succeeded" in events


def test_openai_provider_rate_limit_exhaustion_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INCIDENT_AGENT_OPENAI_API_KEY", "test-key")
    responses = [
        httpx.Response(status_code=429, json={"error": {"message": "rate limited"}}),
        httpx.Response(status_code=429, json={"error": {"message": "rate limited"}}),
    ]

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return responses.pop(0)

    monkeypatch.setattr("incident_agent.llm.openai_provider.httpx.Client", FakeClient)
    provider = OpenAIProvider(max_retries=1, retry_backoff_seconds=0.0)
    with pytest.raises(LLMRateLimitError):
        provider.complete(LLMCompletionRequest(prompt="hello", model="gpt-4.1-mini"))


def test_openai_provider_malformed_json_response_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INCIDENT_AGENT_OPENAI_API_KEY", "test-key")
    responses = [
        httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )
    ]

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return responses.pop(0)

    monkeypatch.setattr("incident_agent.llm.openai_provider.httpx.Client", FakeClient)
    provider = OpenAIProvider(max_retries=0, retry_backoff_seconds=0.0)
    with pytest.raises(LLMResponseFormatError):
        provider.generate_structured_report(
            LLMStructuredReportRequest(prompt="incident", model="gpt-4.1-mini")
        )
