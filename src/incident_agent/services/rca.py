"""Application service for RCA execution."""

from __future__ import annotations

from incident_agent.rca.engine import (
    load_dependency_graph_for_rca,
    load_rca_config,
    perform_rca,
)
from incident_agent.schemas.rca import RCAResult
from incident_agent.services.correlate import correlate_incidents_from_files


def run_rca_from_files(
    *,
    log_path: str,
    metric_path: str,
    config_path: str = "configs/default.yaml",
    bucket_size_minutes: int | None = None,
) -> RCAResult:
    """Correlate incidents and compute RCA artifacts."""

    correlation = correlate_incidents_from_files(
        log_path=log_path,
        metric_path=metric_path,
        config_path=config_path,
        bucket_size_minutes=bucket_size_minutes,
    )
    rca_config = load_rca_config(config_path)
    dependency_graph = load_dependency_graph_for_rca(rca_config)
    return perform_rca(
        correlation.incidents,
        config=rca_config,
        dependency_graph=dependency_graph,
    )
