"""Legacy file-based ingestion wrappers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from incident_agent.ingestion.logs import ingest_logs
from incident_agent.ingestion.metrics import ingest_metrics
from incident_agent.schemas.events import LogEvent, MetricPoint


def load_logs(path: str | Path) -> list[LogEvent]:
    """Load normalized log events from supported file formats."""

    return ingest_logs(path).records


def load_metrics(path: str | Path) -> list[MetricPoint]:
    """Load normalized metric points from supported file formats."""

    return ingest_metrics(path).records


def iter_services(logs: Iterable[LogEvent], metrics: Iterable[MetricPoint]) -> list[str]:
    """Return a sorted list of services present in logs or metrics."""

    names: set[str] = {event.service for event in logs}
    names.update(point.service for point in metrics)
    return sorted(names)
