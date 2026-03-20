"""File-based ingestion utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel

from incident_agent.schemas.events import LogEvent, MetricPoint

TModel = TypeVar("TModel", bound=BaseModel)


def _load_jsonl(path: Path, model: type[TModel]) -> list[TModel]:
    """Load newline-delimited JSON records into typed Pydantic models."""

    records: list[TModel] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line: str = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            records.append(model.model_validate(payload))
    return records


def load_logs(path: str | Path) -> list[LogEvent]:
    """Load normalised log events from a JSONL file."""

    return _load_jsonl(Path(path), LogEvent)


def load_metrics(path: str | Path) -> list[MetricPoint]:
    """Load metric points from a JSONL file."""

    return _load_jsonl(Path(path), MetricPoint)


def iter_services(logs: Iterable[LogEvent], metrics: Iterable[MetricPoint]) -> list[str]:
    """Return a sorted list of services present in logs or metrics."""

    names: set[str] = {event.service for event in logs}
    names.update(point.service for point in metrics)
    return sorted(names)
