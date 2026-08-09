"""Schemas for detected anomalies."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AnomalyType = Literal[
    "error_rate_spike",
    "latency_spike",
    "cpu_anomaly",
    "memory_anomaly",
    "traffic_drop",
    "service_unavailability",
    "error_log_burst",
    "critical_log_burst",
]


class AnomalyCandidate(BaseModel):
    """Structured anomaly candidate produced by a detector."""

    timestamp_window_start: datetime
    timestamp_window_end: datetime
    anomaly_type: AnomalyType
    affected_service: str
    severity_score: float
    observed_value: float
    baseline_value: float
    evidence_summary: str
    scope: Literal["service", "global"] = "service"


class AnomalyDetectionResult(BaseModel):
    """Container for anomaly candidates and metadata."""

    anomalies: list[AnomalyCandidate] = Field(default_factory=list)
