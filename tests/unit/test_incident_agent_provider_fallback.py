from __future__ import annotations

from datetime import datetime

from incident_agent.agents.incident_agent import IncidentAnalysisAgent
from incident_agent.llm.base import BaseLLMProvider, LLMProviderError
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.llm import (
    LLMCompletionRequest,
    LLMCompletionResponse,
    LLMStructuredReportRequest,
    LLMStructuredReportResponse,
)


class FailingProvider(BaseLLMProvider):
    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        raise LLMProviderError("completion unavailable")

    def generate_structured_report(
        self,
        request: LLMStructuredReportRequest,
    ) -> LLMStructuredReportResponse:
        raise LLMProviderError("provider failed")


def test_incident_agent_returns_fallback_report_on_provider_failure() -> None:
    logs = [
        LogEvent(
            timestamp=datetime.fromisoformat("2026-03-20T10:00:00"),
            service="api-service",
            severity="ERROR",
            message="Database timeout",
        )
    ]
    metrics = [
        MetricPoint(
            timestamp=datetime.fromisoformat("2026-03-20T10:00:30"),
            service="api-service",
            metric_name="cpu_usage",
            value=95.0,
        )
    ]

    agent = IncidentAnalysisAgent(provider=FailingProvider(), report_model="mock-model")
    reports = agent.analyze(logs=logs, metrics=metrics)

    assert len(reports) == 1
    assert reports[0].title == "Incident report unavailable"
    assert reports[0].evidence[0].kind == "provider_error"
