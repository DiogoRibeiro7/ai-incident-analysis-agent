"""Application service for incident correlation."""

from __future__ import annotations

from incident_agent.correlation.engine import (
    correlate_anomalies,
    load_correlation_config,
    load_dependency_graph_for_correlation,
)
from incident_agent.schemas.incident import IncidentCorrelationResult
from incident_agent.services.detect import detect_anomalies_from_files


def correlate_incidents_from_files(
    *,
    log_path: str,
    metric_path: str,
    config_path: str = "configs/default.yaml",
    bucket_size_minutes: int | None = None,
) -> IncidentCorrelationResult:
    """Run anomaly detection and correlate anomalies into incident candidates."""

    detection = detect_anomalies_from_files(
        log_path=log_path,
        metric_path=metric_path,
        config_path=config_path,
        bucket_size_minutes=bucket_size_minutes,
    )
    correlation_config = load_correlation_config(config_path)
    dependency_graph = load_dependency_graph_for_correlation(correlation_config)
    return correlate_anomalies(
        detection.anomalies,
        config=correlation_config,
        dependency_graph=dependency_graph,
    )
