"""Mock provider for deterministic local development and tests."""

from __future__ import annotations

import json

from incident_agent.llm.base import BaseLLMProvider
from incident_agent.schemas.llm import (
    LLMCompletionRequest,
    LLMCompletionResponse,
    LLMStructuredReportRequest,
    LLMStructuredReportResponse,
    LLMUsage,
)
from incident_agent.schemas.report import EvidenceItem, IncidentReport


class MockLLMProvider(BaseLLMProvider):
    """Deterministic provider for local and test usage."""

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        content = f"Mock completion for model={request.model}. Prompt size={len(request.prompt)}."
        token_estimate = max(1, len(request.prompt) // 4)
        return LLMCompletionResponse(
            model=request.model,
            content=content,
            raw_response={},
            usage=LLMUsage(
                prompt_tokens=token_estimate,
                completion_tokens=max(1, len(content) // 4),
                total_tokens=token_estimate + max(1, len(content) // 4),
                latency_ms=1.0,
                estimated_cost_usd=0.0,
            ),
        )

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
            usage=LLMUsage(
                prompt_tokens=max(1, len(request.prompt) // 4),
                completion_tokens=max(1, len(report.model_dump_json()) // 4),
                total_tokens=max(1, len(request.prompt) // 4)
                + max(1, len(report.model_dump_json()) // 4),
                latency_ms=1.0,
                estimated_cost_usd=0.0,
            ),
        )


# Backward compatibility alias.
MockLLMClient = MockLLMProvider
