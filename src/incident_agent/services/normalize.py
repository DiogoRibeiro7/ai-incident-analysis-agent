"""Application service for timeline normalization and alignment."""

from __future__ import annotations

from incident_agent.ingestion import ingest_logs, ingest_metrics
from incident_agent.normalization.timeline import (
    NormalizationConfig,
    align_events_to_timeline,
    load_normalization_config,
)
from incident_agent.schemas.timeline import TimelineAlignmentResult


def normalize_from_files(
    *,
    log_path: str,
    metric_path: str,
    config_path: str = "configs/default.yaml",
    bucket_size_minutes: int | None = None,
) -> TimelineAlignmentResult:
    """Load logs and metrics and align them on a shared timeline."""

    logs = ingest_logs(log_path).records
    metrics = ingest_metrics(metric_path).records
    config = load_normalization_config(config_path)
    if bucket_size_minutes is not None:
        config = NormalizationConfig(
            **{
                **config.model_dump(),
                "bucket_size_minutes": bucket_size_minutes,
            }
        )
    return align_events_to_timeline(logs, metrics, config=config)
