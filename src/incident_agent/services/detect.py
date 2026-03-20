"""Application service for anomaly detection."""

from __future__ import annotations

from incident_agent.anomaly_detection.engine import (
    detect_anomalies,
    load_anomaly_detection_config,
)
from incident_agent.normalization.timeline import load_normalization_config
from incident_agent.schemas.anomaly import AnomalyDetectionResult
from incident_agent.services.normalize import normalize_from_files


def detect_anomalies_from_files(
    *,
    log_path: str,
    metric_path: str,
    config_path: str = "configs/default.yaml",
    bucket_size_minutes: int | None = None,
) -> AnomalyDetectionResult:
    """Normalize events and run anomaly detectors."""

    alignment = normalize_from_files(
        log_path=log_path,
        metric_path=metric_path,
        config_path=config_path,
        bucket_size_minutes=bucket_size_minutes,
    )
    normalization_config = load_normalization_config(config_path)
    effective_bucket_size = (
        bucket_size_minutes
        if bucket_size_minutes is not None
        else normalization_config.bucket_size_minutes
    )
    config = load_anomaly_detection_config(config_path)
    return detect_anomalies(
        alignment,
        bucket_size_minutes=effective_bucket_size,
        config=config,
    )
