"""Schemas for normalized timeline events and bucketed features."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

TimelineSignal = Literal[
    "log",
    "latency",
    "cpu",
    "memory",
    "http_error_rate",
    "error_log_count",
    "critical_log_count",
    "heartbeat",
    "service_failure",
    "metric_other",
]


class MissingBucketPolicy(StrEnum):
    """Semantic policy for an expected metric that is absent in a time bucket."""

    ZERO = "zero"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


class TimelineEvent(BaseModel):
    """Unified event representation for aligned incident timelines."""

    timestamp: datetime
    bucket_start: datetime
    service: str
    source: Literal["log", "metric"]
    signal: TimelineSignal
    synthetic: bool = False
    missing_policy: MissingBucketPolicy | None = None
    severity: str | None = None
    value: float | None = None
    unit: str | None = None
    message: str | None = None
    metric_name: str | None = None


class TimelineBucketFeatures(BaseModel):
    """Aggregated timeline features for one time bucket."""

    bucket_start: datetime
    bucket_end: datetime
    event_count: int
    synthetic_event_count: int = 0
    log_count: int
    error_count: int
    error_log_count: int = 0
    critical_log_count: int = 0
    warn_count: int
    unique_services_affected: int
    log_spike: bool
    error_burst: bool
    service_failure_signals: int
    zero_filled_metric_count: int = 0
    unavailable_missing_metric_count: int = 0
    unknown_missing_metric_count: int = 0
    http_error_rate: float | None = None
    p95_latency: float | None = None
    cpu_mean: float | None = None
    cpu_max: float | None = None
    memory_mean: float | None = None
    memory_max: float | None = None


class TimelineAlignmentResult(BaseModel):
    """Normalized events and derived bucket features."""

    events: list[TimelineEvent] = Field(default_factory=list)
    buckets: list[TimelineBucketFeatures] = Field(default_factory=list)
