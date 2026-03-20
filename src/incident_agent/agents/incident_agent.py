"""Agent orchestration for incident analysis."""

from __future__ import annotations

from incident_agent.analysis.correlator import correlate_incidents
from incident_agent.llm.base import BaseLLMProvider, LLMProviderError
from incident_agent.prompts.builders import build_incident_prompt
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.report import EvidenceItem, IncidentReport


class IncidentAnalysisAgent:
    """Coordinates correlation, prompting, and report generation."""

    def __init__(self, provider: BaseLLMProvider, report_model: str) -> None:
        self._provider = provider
        self._report_model = report_model

    def analyze(self, logs: list[LogEvent], metrics: list[MetricPoint]) -> list[IncidentReport]:
        """Analyze events and return one report per candidate incident."""

        incidents = correlate_incidents(logs, metrics)
        reports: list[IncidentReport] = []
        for incident in incidents:
            prompt = build_incident_prompt(incident)
            try:
                report = self._provider.generate_incident_report(
                    prompt=prompt,
                    model=self._report_model,
                )
            except LLMProviderError as error:
                report = IncidentReport(
                    title="Incident report unavailable",
                    severity="unknown",
                    impacted_service=incident.service,
                    incident_summary="LLM provider failed while generating the report.",
                    likely_root_causes=[],
                    recommended_actions=[
                        "Retry with mock provider or inspect provider configuration."
                    ],
                    evidence=[
                        EvidenceItem(
                            kind="provider_error",
                            timestamp=incident.start_time.isoformat(),
                            content=str(error),
                        )
                    ],
                )
            reports.append(report)
        return reports
