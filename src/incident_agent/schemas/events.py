"""Schemas for logs, metrics, and correlated incidents."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LogEvent(BaseModel):
    """Normalised application or infrastructure log event."""

    timestamp: datetime
    service: str
    severity: Literal["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]
    message: str
    trace_id: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class MetricPoint(BaseModel):
    """Single metric observation for a service."""

    timestamp: datetime
    service: str
    metric_name: str
    value: float
    unit: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class IncidentCandidate(BaseModel):
    """Candidate incident produced by heuristic correlation logic."""

    incident_id: str
    service: str
    start_time: datetime
    end_time: datetime
    summary: str
    related_logs: list[LogEvent] = Field(default_factory=list)
    related_metrics: list[MetricPoint] = Field(default_factory=list)
