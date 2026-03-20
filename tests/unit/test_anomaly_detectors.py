from __future__ import annotations

from datetime import UTC, datetime, timedelta

from incident_agent.anomaly_detection.availability import detect_service_unavailability
from incident_agent.anomaly_detection.common import DetectorThresholds, SeriesPoint
from incident_agent.anomaly_detection.cpu import detect_cpu_anomalies
from incident_agent.anomaly_detection.error_rate import detect_error_rate_spikes
from incident_agent.anomaly_detection.latency import detect_latency_spikes
from incident_agent.anomaly_detection.memory import detect_memory_anomalies
from incident_agent.anomaly_detection.traffic import detect_traffic_drops


def _series(values: list[float], *, service: str = "svc") -> list[SeriesPoint]:
    start = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
    points: list[SeriesPoint] = []
    for index, value in enumerate(values):
        bucket_start = start + timedelta(minutes=5 * index)
        points.append(
            SeriesPoint(
                bucket_start=bucket_start,
                bucket_end=bucket_start + timedelta(minutes=5),
                service=service,
                value=value,
                scope="service",
            )
        )
    return points


def _thresholds() -> DetectorThresholds:
    return DetectorThresholds(
        min_support=3,
        lookback_windows=10,
        z_threshold=2.0,
        mad_multiplier=2.0,
        min_relative_change=0.1,
    )


def test_detect_error_rate_spike() -> None:
    anomalies = detect_error_rate_spikes(
        _series([0.01, 0.012, 0.011, 0.25]),
        thresholds=_thresholds(),
    )
    assert anomalies
    assert anomalies[0].anomaly_type == "error_rate_spike"


def test_detect_latency_spike() -> None:
    anomalies = detect_latency_spikes(
        _series([120.0, 125.0, 130.0, 1500.0]),
        thresholds=_thresholds(),
    )
    assert anomalies
    assert anomalies[0].anomaly_type == "latency_spike"


def test_detect_cpu_anomaly() -> None:
    anomalies = detect_cpu_anomalies(
        _series([35.0, 36.0, 34.0, 96.0]),
        thresholds=_thresholds(),
    )
    assert anomalies
    assert anomalies[0].anomaly_type == "cpu_anomaly"


def test_detect_memory_anomaly() -> None:
    anomalies = detect_memory_anomalies(
        _series([400.0, 410.0, 405.0, 1200.0]),
        thresholds=_thresholds(),
    )
    assert anomalies
    assert anomalies[0].anomaly_type == "memory_anomaly"


def test_detect_traffic_drop() -> None:
    anomalies = detect_traffic_drops(
        _series([1200.0, 1250.0, 1180.0, 120.0]),
        thresholds=_thresholds(),
    )
    assert anomalies
    assert anomalies[0].anomaly_type == "traffic_drop"


def test_detect_service_unavailability_spike() -> None:
    anomalies = detect_service_unavailability(
        _series([0.0, 0.0, 0.0, 1.0]),
        thresholds=_thresholds(),
    )
    assert anomalies
    assert anomalies[0].anomaly_type == "service_unavailability"
