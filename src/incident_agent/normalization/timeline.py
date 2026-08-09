"""Time normalization and alignment across logs and metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean

from pydantic import BaseModel, Field, field_validator

from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.timeline import (
    MissingBucketPolicy,
    TimelineAlignmentResult,
    TimelineBucketFeatures,
    TimelineEvent,
    TimelineSignal,
)


class NormalizationConfig(BaseModel):
    """Configuration for timeline alignment and bucketing."""

    bucket_size_minutes: int = 5
    log_spike_threshold: int = 4
    error_burst_threshold: int = 2
    latency_metrics: set[str] = Field(
        default_factory=lambda: {"request_latency_ms", "latency_ms", "p95_latency_ms"}
    )
    cpu_metrics: set[str] = Field(default_factory=lambda: {"cpu_usage", "cpu_percent"})
    memory_metrics: set[str] = Field(
        default_factory=lambda: {"memory_usage", "memory_usage_mb", "memory_used_mb"}
    )
    http_error_rate_metrics: set[str] = Field(
        default_factory=lambda: {"error_rate", "http_error_rate", "http_5xx_error_rate"}
    )
    service_failure_metrics: set[str] = Field(
        default_factory=lambda: {"upstream_failure_rate", "service_unavailable"}
    )
    metric_missing_policies: dict[str, MissingBucketPolicy] = Field(
        default_factory=lambda: {
            "request_count": MissingBucketPolicy.ZERO,
            "traffic": MissingBucketPolicy.ZERO,
            "throughput": MissingBucketPolicy.ZERO,
            "rps": MissingBucketPolicy.ZERO,
            "heartbeat": MissingBucketPolicy.UNAVAILABLE,
            "cpu_usage": MissingBucketPolicy.MISSING,
            "cpu_percent": MissingBucketPolicy.MISSING,
            "request_latency_ms": MissingBucketPolicy.MISSING,
            "latency_ms": MissingBucketPolicy.MISSING,
            "p95_latency_ms": MissingBucketPolicy.MISSING,
        }
    )

    @field_validator("bucket_size_minutes")
    @classmethod
    def validate_bucket_size(cls, value: int) -> int:
        """Allow only required bucket sizes from the prompt."""

        if value not in {1, 5, 15}:
            raise ValueError("bucket_size_minutes must be one of: 1, 5, 15")
        return value


def load_normalization_config(path: str | Path = "configs/default.yaml") -> NormalizationConfig:
    """Load normalization config from YAML."""

    loaded = load_settings_from_yaml(Path(path))
    section = loaded.get("normalization", {})
    if not isinstance(section, dict):
        raise ValueError("The 'normalization' section must be a mapping.")
    return NormalizationConfig.model_validate(section)


def align_events_to_timeline(
    logs: list[LogEvent],
    metrics: list[MetricPoint],
    *,
    config: NormalizationConfig,
    analysis_start: datetime | None = None,
    analysis_end: datetime | None = None,
) -> TimelineAlignmentResult:
    """Normalize timestamps, sort events, assign buckets, and aggregate features."""

    events: list[TimelineEvent] = []
    for log in logs:
        timestamp = _to_utc(log.timestamp)
        events.append(
            TimelineEvent(
                timestamp=timestamp,
                bucket_start=_bucket_floor(timestamp, config.bucket_size_minutes),
                service=log.service,
                source="log",
                signal=_log_signal(log.severity),
                severity=log.severity,
                value=1.0 if log.severity in {"ERROR", "CRITICAL"} else None,
                message=log.message,
            )
        )

    for metric in metrics:
        timestamp = _to_utc(metric.timestamp)
        events.append(
            TimelineEvent(
                timestamp=timestamp,
                bucket_start=_bucket_floor(timestamp, config.bucket_size_minutes),
                service=metric.service,
                source="metric",
                signal=_metric_signal(metric.metric_name, config),
                value=metric.value,
                unit=metric.unit,
                metric_name=metric.metric_name,
            )
        )

    if events or analysis_start is not None or analysis_end is not None:
        events.extend(
            _missing_bucket_events(
                events=events,
                config=config,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
            )
        )

    ordered_events = sorted(
        events,
        key=lambda item: (
            item.bucket_start,
            item.timestamp,
            item.service,
            item.signal,
            item.source,
        ),
    )

    buckets: dict[datetime, list[TimelineEvent]] = {}
    for event in ordered_events:
        buckets.setdefault(event.bucket_start, []).append(event)

    for bucket_start in _bucket_grid(
        events=ordered_events,
        config=config,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
    ):
        buckets.setdefault(bucket_start, [])

    ordered_buckets = [
        _summarize_bucket(bucket_start, bucket_events, config)
        for bucket_start, bucket_events in sorted(buckets.items(), key=lambda item: item[0])
    ]

    return TimelineAlignmentResult(events=ordered_events, buckets=ordered_buckets)


def _to_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _bucket_floor(timestamp: datetime, bucket_size_minutes: int) -> datetime:
    bucket_seconds = bucket_size_minutes * 60
    epoch_seconds = int(timestamp.timestamp())
    floored_seconds = epoch_seconds - (epoch_seconds % bucket_seconds)
    return datetime.fromtimestamp(floored_seconds, tz=UTC)


def _bucket_grid(
    *,
    events: list[TimelineEvent],
    config: NormalizationConfig,
    analysis_start: datetime | None,
    analysis_end: datetime | None,
) -> list[datetime]:
    start_candidates = [event.bucket_start for event in events]
    end_candidates = [event.bucket_start for event in events]
    if analysis_start is not None:
        start_candidates.append(_bucket_floor(_to_utc(analysis_start), config.bucket_size_minutes))
    if analysis_end is not None:
        end_candidates.append(_bucket_floor(_to_utc(analysis_end), config.bucket_size_minutes))
    if not start_candidates or not end_candidates:
        return []

    current = min(start_candidates)
    final = max(end_candidates)
    step = timedelta(minutes=config.bucket_size_minutes)
    buckets = []
    while current <= final:
        buckets.append(current)
        current += step
    return buckets


def _log_signal(severity: str) -> TimelineSignal:
    if severity == "ERROR":
        return "error_log_count"
    if severity == "CRITICAL":
        return "critical_log_count"
    return "log"


def _metric_signal(metric_name: str, config: NormalizationConfig) -> TimelineSignal:
    lowered = metric_name.lower()
    latency_metrics = {name.lower() for name in config.latency_metrics}
    cpu_metrics = {name.lower() for name in config.cpu_metrics}
    memory_metrics = {name.lower() for name in config.memory_metrics}
    http_error_rate_metrics = {name.lower() for name in config.http_error_rate_metrics}
    service_failure_metrics = {name.lower() for name in config.service_failure_metrics}

    if "heartbeat" in lowered:
        return "heartbeat"
    if lowered in latency_metrics or "latency" in lowered:
        return "latency"
    if lowered in cpu_metrics or "cpu" in lowered:
        return "cpu"
    if lowered in memory_metrics or "memory" in lowered:
        return "memory"
    if lowered in http_error_rate_metrics or "error_rate" in lowered:
        return "http_error_rate"
    if lowered in service_failure_metrics:
        return "service_failure"
    return "metric_other"


def _missing_bucket_events(
    *,
    events: list[TimelineEvent],
    config: NormalizationConfig,
    analysis_start: datetime | None,
    analysis_end: datetime | None,
) -> list[TimelineEvent]:
    observed_metric_names_by_service: dict[str, set[str]] = {}
    observed_metric_keys: set[tuple[datetime, str, str]] = set()
    for event in events:
        if event.source != "metric" or event.metric_name is None:
            continue
        metric_name = event.metric_name
        observed_metric_names_by_service.setdefault(event.service, set()).add(metric_name)
        observed_metric_keys.add((event.bucket_start, event.service, metric_name.lower()))

    synthetic_events: list[TimelineEvent] = []
    for bucket_start in _bucket_grid(
        events=events,
        config=config,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
    ):
        for service, metric_names in sorted(observed_metric_names_by_service.items()):
            for metric_name in sorted(metric_names):
                if (bucket_start, service, metric_name.lower()) in observed_metric_keys:
                    continue
                policy = _missing_policy(metric_name, config)
                value = _missing_value(policy)
                synthetic_events.append(
                    TimelineEvent(
                        timestamp=bucket_start,
                        bucket_start=bucket_start,
                        service=service,
                        source="metric",
                        signal=_metric_signal(metric_name, config),
                        value=value,
                        metric_name=metric_name,
                        synthetic=True,
                        missing_policy=policy,
                    )
                )
    return synthetic_events


def _missing_policy(metric_name: str, config: NormalizationConfig) -> MissingBucketPolicy:
    lowered = metric_name.lower()
    policy_map = {name.lower(): policy for name, policy in config.metric_missing_policies.items()}
    if lowered in policy_map:
        return policy_map[lowered]
    for name, policy in policy_map.items():
        if name in lowered:
            return policy
    return MissingBucketPolicy.MISSING


def _missing_value(policy: MissingBucketPolicy) -> float | None:
    if policy == MissingBucketPolicy.ZERO:
        return 0.0
    if policy == MissingBucketPolicy.UNAVAILABLE:
        return 1.0
    return None


def _summarize_bucket(
    bucket_start: datetime,
    events: list[TimelineEvent],
    config: NormalizationConfig,
) -> TimelineBucketFeatures:
    bucket_end = bucket_start + timedelta(minutes=config.bucket_size_minutes)
    observed_events = [event for event in events if not event.synthetic]
    synthetic_events = [event for event in events if event.synthetic]
    log_events = [event for event in observed_events if event.source == "log"]
    error_log_count = sum(1 for event in log_events if event.signal == "error_log_count")
    critical_log_count = sum(1 for event in log_events if event.signal == "critical_log_count")
    error_count = error_log_count + critical_log_count
    warn_count = sum(1 for event in log_events if event.severity == "WARN")
    service_failure_signals = sum(1 for event in events if event.signal == "service_failure")

    latency_values = _metric_values(events, signal="latency")
    cpu_values = _metric_values(events, signal="cpu")
    memory_values = _metric_values(events, signal="memory")
    http_error_rate_values = _metric_values(events, signal="http_error_rate")

    return TimelineBucketFeatures(
        bucket_start=bucket_start,
        bucket_end=bucket_end,
        event_count=len(observed_events),
        synthetic_event_count=len(synthetic_events),
        log_count=len(log_events),
        error_count=error_count,
        error_log_count=error_log_count,
        critical_log_count=critical_log_count,
        warn_count=warn_count,
        unique_services_affected=len({event.service for event in observed_events}),
        log_spike=len(log_events) >= config.log_spike_threshold,
        error_burst=error_count >= config.error_burst_threshold,
        service_failure_signals=service_failure_signals,
        zero_filled_metric_count=sum(
            1 for event in synthetic_events if event.missing_policy == MissingBucketPolicy.ZERO
        ),
        unavailable_missing_metric_count=sum(
            1
            for event in synthetic_events
            if event.missing_policy == MissingBucketPolicy.UNAVAILABLE
        ),
        unknown_missing_metric_count=sum(
            1 for event in synthetic_events if event.missing_policy == MissingBucketPolicy.MISSING
        ),
        http_error_rate=mean(http_error_rate_values) if http_error_rate_values else None,
        p95_latency=_percentile(latency_values, percentile=95),
        cpu_mean=mean(cpu_values) if cpu_values else None,
        cpu_max=max(cpu_values) if cpu_values else None,
        memory_mean=mean(memory_values) if memory_values else None,
        memory_max=max(memory_values) if memory_values else None,
    )


def _metric_values(events: list[TimelineEvent], *, signal: str) -> list[float]:
    return [event.value for event in events if event.signal == signal and event.value is not None]


def _percentile(values: list[float], *, percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = round((percentile / 100) * (len(ordered) - 1))
    return ordered[rank]
