"""Mock provider for deterministic local development and tests."""

from __future__ import annotations

import json

from incident_agent.llm.base import BaseLLMProvider
from incident_agent.schemas.llm import (
    LLMCompletionRequest,
    LLMCompletionResponse,
    LLMStructuredReportRequest,
    LLMStructuredReportResponse,
)
from incident_agent.schemas.report import EvidenceItem, IncidentReport


class MockLLMProvider(BaseLLMProvider):
    """Deterministic provider for local and test usage."""

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        content = f"Mock completion for model={request.model}. Prompt size={len(request.prompt)}."
        return LLMCompletionResponse(model=request.model, content=content, raw_response={})

    def generate_structured_report(
        self,
        request: LLMStructuredReportRequest,
    ) -> LLMStructuredReportResponse:
        report = IncidentReport(
            title="Mock incident report",
            severity="high",
            impacted_service="api-service",
            incident_summary=(
                "High-severity log events and related metrics suggest a service disruption."
            ),
            likely_root_causes=[
                "Application errors increased during the incident window.",
                "Metric anomalies indicate possible resource or dependency issues.",
            ],
            recommended_actions=[
                "Inspect recent deployments and configuration changes.",
                "Check upstream dependencies and saturation metrics.",
            ],
            evidence=[
                EvidenceItem(
                    kind="prompt_excerpt",
                    timestamp="n/a",
                    content=request.prompt[:160],
                )
            ],
        )
        return LLMStructuredReportResponse(
            model=request.model,
            content=json.dumps(report.model_dump(mode="json")),
            raw_response={"provider": "mock"},
        )


# Backward compatibility alias.
MockLLMClient = MockLLMProvider
