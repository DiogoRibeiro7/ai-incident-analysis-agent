"""Application service for timeline normalization and alignment."""

from __future__ import annotations

from pathlib import Path

from incident_agent.ingest.files import load_logs, load_metrics
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

    logs = load_logs(Path(log_path))
    metrics = load_metrics(Path(metric_path))
    config = load_normalization_config(config_path)
    if bucket_size_minutes is not None:
        config = NormalizationConfig(
            **{
                **config.model_dump(),
                "bucket_size_minutes": bucket_size_minutes,
            }
        )
    return align_events_to_timeline(logs, metrics, config=config)
