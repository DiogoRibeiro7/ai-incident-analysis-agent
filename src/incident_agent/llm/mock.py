"""Mock LLM implementation for deterministic local development."""

from __future__ import annotations

from incident_agent.schemas.report import EvidenceItem, IncidentReport


class MockLLMClient:
    """Very small local stand-in for a real LLM backend."""

    def generate_incident_report(self, prompt: str) -> IncidentReport:
        """Return a deterministic report without external dependencies."""

        return IncidentReport(
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
                    content=prompt[:160],
                )
            ],
        )
