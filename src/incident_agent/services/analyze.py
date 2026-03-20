"""Application service for end-to-end incident analysis."""

from __future__ import annotations

from incident_agent.agents.incident_agent import IncidentAnalysisAgent
from incident_agent.ingest.files import load_logs, load_metrics
from incident_agent.llm.mock import MockLLMClient
from incident_agent.schemas.report import IncidentReport


def analyze_from_files(log_path: str, metric_path: str) -> list[IncidentReport]:
    """Load logs and metrics from files and return incident reports."""

    logs = load_logs(log_path)
    metrics = load_metrics(metric_path)
    agent = IncidentAnalysisAgent(llm_client=MockLLMClient())
    return agent.analyze(logs=logs, metrics=metrics)
