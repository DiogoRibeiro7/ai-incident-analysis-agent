"""Agent orchestration for incident analysis."""

from __future__ import annotations

from incident_agent.analysis.correlator import correlate_incidents
from incident_agent.llm.base import LLMClient
from incident_agent.prompts.builders import build_incident_prompt
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.report import IncidentReport


class IncidentAnalysisAgent:
    """Coordinates correlation, prompting, and report generation."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def analyze(self, logs: list[LogEvent], metrics: list[MetricPoint]) -> list[IncidentReport]:
        """Analyze events and return one report per candidate incident."""

        incidents = correlate_incidents(logs, metrics)
        reports: list[IncidentReport] = []
        for incident in incidents:
            prompt = build_incident_prompt(incident)
            report = self._llm_client.generate_incident_report(prompt)
            reports.append(report)
        return reports
