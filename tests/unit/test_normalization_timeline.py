from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from incident_agent.anomaly_detection.common import DetectorThresholds
from incident_agent.anomaly_detection.engine import (
    AnomalyDetectionConfig,
    _build_points,
    detect_anomalies,
)
from incident_agent.normalization.timeline import (
    NormalizationConfig,
    align_events_to_timeline,
    load_normalization_config,
)
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.timeline import MissingBucketPolicy


def test_align_events_handles_timezone_and_bucketing() -> None:
    logs = [
        LogEvent(
            timestamp=datetime.fromisoformat("2026-03-20T10:00:30+01:00"),
            service="api",
            severity="ERROR",
            message="failure",
        ),
        LogEvent(
            timestamp=datetime.fromisoformat("2026-03-20T09:01:10"),
            service="api",
            severity="WARN",
            message="warn",
        ),
    ]
    metrics = [
        MetricPoint(
            timestamp=datetime.fromisoformat("2026-03-20T09:00:40Z"),
            service="api",
            metric_name="request_latency_ms",
            value=500.0,
        ),
        MetricPoint(
            timestamp=datetime.fromisoformat("2026-03-20T09:01:20Z"),
            service="api",
            metric_name="cpu_usage",
            value=88.0,
        ),
    ]

    result = align_events_to_timeline(
        logs,
        metrics,
        config=NormalizationConfig(bucket_size_minutes=1, log_spike_threshold=1),
    )

    observed_events = [event for event in result.events if not event.synthetic]
    assert len(observed_events) == 4
    assert sum(1 for event in result.events if event.synthetic) == 2
    assert observed_events[0].timestamp.isoformat() == "2026-03-20T09:00:30+00:00"
    assert all(event.timestamp.tzinfo is not None for event in observed_events)
    assert [bucket.bucket_start.isoformat() for bucket in result.buckets] == [
        "2026-03-20T09:00:00+00:00",
        "2026-03-20T09:01:00+00:00",
    ]
    first_bucket = result.buckets[0]
    assert first_bucket.error_count == 1
    assert first_bucket.p95_latency == 500.0
    assert first_bucket.log_spike is True


def test_align_events_is_deterministic_and_stable() -> None:
    logs = [
        LogEvent(
            timestamp=datetime.fromisoformat("2026-03-20T09:00:20Z"),
            service="worker",
            severity="ERROR",
            message="boom",
        ),
        LogEvent(
            timestamp=datetime.fromisoformat("2026-03-20T09:00:10Z"),
            service="api",
            severity="WARN",
            message="warn",
        ),
    ]
    metrics = [
        MetricPoint(
            timestamp=datetime.fromisoformat("2026-03-20T09:00:15Z"),
            service="api",
            metric_name="memory_usage_mb",
            value=350.0,
        ),
        MetricPoint(
            timestamp=datetime.fromisoformat("2026-03-20T09:00:16Z"),
            service="api",
            metric_name="memory_usage_mb",
            value=450.0,
        ),
    ]

    config = NormalizationConfig(bucket_size_minutes=5, error_burst_threshold=1)
    first = align_events_to_timeline(logs, metrics, config=config)
    second = align_events_to_timeline(logs, metrics, config=config)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.events[0].service == "api"
    assert first.buckets[0].memory_mean == 400.0
    assert first.buckets[0].memory_max == 450.0
    assert first.buckets[0].error_burst is True


def test_error_rates_and_log_counts_keep_separate_units() -> None:
    timestamp = datetime.fromisoformat("2026-03-20T09:00:00Z")
    logs = [
        LogEvent(
            timestamp=timestamp,
            service="api",
            severity="ERROR",
            message=f"error {index}",
        )
        for index in range(10)
    ]
    logs.extend(
        LogEvent(
            timestamp=timestamp,
            service="api",
            severity="CRITICAL",
            message=f"critical {index}",
        )
        for index in range(3)
    )
    metrics = [
        MetricPoint(
            timestamp=timestamp,
            service="api",
            metric_name="error_rate",
            value=0.02,
            unit="ratio",
        )
    ]

    result = align_events_to_timeline(
        logs,
        metrics,
        config=NormalizationConfig(bucket_size_minutes=5),
    )
    bucket = result.buckets[0]
    error_rate_points = _build_points(
        result.events,
        metric_kind="http_error_rate",
        agg="mean",
        bucket_size_minutes=5,
    )

    assert bucket.http_error_rate == 0.02
    assert bucket.error_log_count == 10
    assert bucket.critical_log_count == 3
    assert bucket.error_count == 13
    assert [event.value for event in result.events if event.signal == "http_error_rate"] == [0.02]
    assert (
        sum(event.value or 0.0 for event in result.events if event.signal == "error_log_count")
        == 10
    )
    assert all(event.signal != "service_failure" for event in result.events)
    assert {point.value for point in error_rate_points} == {0.02}


def test_log_count_bursts_are_separate_detection_evidence() -> None:
    start = datetime.fromisoformat("2026-03-20T09:00:00Z")
    metrics = [
        MetricPoint(
            timestamp=start.replace(minute=index * 5),
            service="api",
            metric_name="error_rate",
            value=0.02,
            unit="ratio",
        )
        for index in range(6)
    ]
    burst_time = start.replace(minute=25)
    logs = [
        LogEvent(
            timestamp=burst_time,
            service="api",
            severity="ERROR",
            message=f"error {index}",
        )
        for index in range(10)
    ]
    logs.extend(
        LogEvent(
            timestamp=burst_time,
            service="api",
            severity="CRITICAL",
            message=f"critical {index}",
        )
        for index in range(2)
    )
    alignment = align_events_to_timeline(
        logs,
        metrics,
        config=NormalizationConfig(bucket_size_minutes=5),
    )

    result = detect_anomalies(
        alignment,
        bucket_size_minutes=5,
        config=AnomalyDetectionConfig(
            error_rate=DetectorThresholds(min_support=3),
            error_logs=DetectorThresholds(min_support=3),
            critical_logs=DetectorThresholds(min_support=3),
        ),
    )

    anomaly_types = {anomaly.anomaly_type for anomaly in result.anomalies}
    assert "error_log_burst" in anomaly_types
    assert "critical_log_burst" in anomaly_types
    assert "error_rate_spike" not in anomaly_types


def test_missing_request_count_can_mean_zero_for_traffic_disappearance() -> None:
    start = datetime.fromisoformat("2026-03-20T09:00:00Z")
    metrics = [
        MetricPoint(
            timestamp=start + timedelta(minutes=index * 5),
            service="api",
            metric_name="request_count",
            value=100.0,
            unit="count",
        )
        for index in range(5)
    ]

    alignment = align_events_to_timeline(
        [],
        metrics,
        config=NormalizationConfig(bucket_size_minutes=5),
        analysis_end=start + timedelta(minutes=25),
    )
    last_bucket = alignment.buckets[-1]

    result = detect_anomalies(
        alignment,
        bucket_size_minutes=5,
        config=AnomalyDetectionConfig(),
    )

    assert last_bucket.bucket_start == start + timedelta(minutes=25)
    assert last_bucket.zero_filled_metric_count == 1
    assert any(
        event.metric_name == "request_count"
        and event.synthetic
        and event.value == 0.0
        and event.missing_policy == MissingBucketPolicy.ZERO
        for event in alignment.events
    )
    assert "traffic_drop" in {anomaly.anomaly_type for anomaly in result.anomalies}


def test_missing_request_count_can_remain_unknown() -> None:
    start = datetime.fromisoformat("2026-03-20T09:00:00Z")
    metrics = [
        MetricPoint(
            timestamp=start + timedelta(minutes=index * 5),
            service="api",
            metric_name="request_count",
            value=100.0,
            unit="count",
        )
        for index in range(5)
    ]
    config = NormalizationConfig(
        bucket_size_minutes=5,
        metric_missing_policies={"request_count": MissingBucketPolicy.MISSING},
    )

    alignment = align_events_to_timeline(
        [],
        metrics,
        config=config,
        analysis_end=start + timedelta(minutes=25),
    )
    traffic_points = _build_points(
        alignment.events,
        metric_kind="traffic",
        agg="sum",
        bucket_size_minutes=5,
    )
    result = detect_anomalies(
        alignment,
        bucket_size_minutes=5,
        config=AnomalyDetectionConfig(),
    )

    assert alignment.buckets[-1].unknown_missing_metric_count == 1
    assert all(point.value == 100.0 for point in traffic_points)
    assert "traffic_drop" not in {anomaly.anomaly_type for anomaly in result.anomalies}


def test_missing_cpu_observation_is_unknown_not_zero() -> None:
    start = datetime.fromisoformat("2026-03-20T09:00:00Z")
    metrics = [
        MetricPoint(
            timestamp=start + timedelta(minutes=index * 5),
            service="api",
            metric_name="cpu_usage",
            value=55.0,
            unit="percent",
        )
        for index in range(5)
    ]

    alignment = align_events_to_timeline(
        [],
        metrics,
        config=NormalizationConfig(bucket_size_minutes=5),
        analysis_end=start + timedelta(minutes=25),
    )
    cpu_points = _build_points(
        alignment.events,
        metric_kind="cpu",
        agg="mean",
        bucket_size_minutes=5,
    )

    assert alignment.buckets[-1].unknown_missing_metric_count == 1
    assert all(point.value == 55.0 for point in cpu_points)
    assert not any(point.bucket_start == start + timedelta(minutes=25) for point in cpu_points)


def test_missing_heartbeat_represents_unavailable() -> None:
    start = datetime.fromisoformat("2026-03-20T09:00:00Z")
    metrics = [
        MetricPoint(
            timestamp=start + timedelta(minutes=index * 5),
            service="api",
            metric_name="heartbeat",
            value=1.0,
        )
        for index in range(5)
    ]

    alignment = align_events_to_timeline(
        [],
        metrics,
        config=NormalizationConfig(bucket_size_minutes=5),
        analysis_end=start + timedelta(minutes=25),
    )
    result = detect_anomalies(
        alignment,
        bucket_size_minutes=5,
        config=AnomalyDetectionConfig(),
    )

    assert alignment.buckets[-1].unavailable_missing_metric_count == 1
    assert any(
        event.metric_name == "heartbeat"
        and event.synthetic
        and event.value == 1.0
        and event.missing_policy == MissingBucketPolicy.UNAVAILABLE
        for event in alignment.events
    )
    assert "service_unavailability" in {anomaly.anomaly_type for anomaly in result.anomalies}


def test_load_normalization_config_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "normalization:",
                "  bucket_size_minutes: 15",
                "  log_spike_threshold: 3",
                "  error_burst_threshold: 2",
                "  latency_metrics: [request_latency_ms]",
                "  cpu_metrics: [cpu_usage]",
                "  memory_metrics: [memory_usage_mb]",
                "  http_error_rate_metrics: [error_rate]",
                "  service_failure_metrics: [error_rate]",
                "  metric_missing_policies:",
                "    request_count: zero",
                "    heartbeat: unavailable",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_normalization_config(config_path)

    assert loaded.bucket_size_minutes == 15
    assert loaded.log_spike_threshold == 3
    assert loaded.metric_missing_policies["request_count"] == MissingBucketPolicy.ZERO
    assert loaded.metric_missing_policies["heartbeat"] == MissingBucketPolicy.UNAVAILABLE
