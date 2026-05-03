"""Application service for end-to-end incident analysis."""

from __future__ import annotations

from incident_agent.agents.incident_agent import IncidentAnalysisAgent
from incident_agent.ingestion import ingest_logs, ingest_metrics
from incident_agent.llm.factory import create_provider, load_llm_config
from incident_agent.schemas.report import IncidentReport


def analyze_from_files(
    log_path: str,
    metric_path: str,
    *,
    config_path: str = "configs/default.yaml",
) -> list[IncidentReport]:
    """Load logs and metrics from files and return incident reports."""

    logs = ingest_logs(log_path).records
    metrics = ingest_metrics(metric_path).records
    llm_config = load_llm_config(config_path)
    provider = create_provider(llm_config, config_path=config_path)
    agent = IncidentAnalysisAgent(provider=provider, report_model=llm_config.report_model)
    return agent.analyze(logs=logs, metrics=metrics)
