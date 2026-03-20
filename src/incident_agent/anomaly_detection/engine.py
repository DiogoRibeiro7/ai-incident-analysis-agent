"""Anomaly detection orchestration over aligned timeline events."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean

from pydantic import BaseModel, Field

from incident_agent.anomaly_detection.availability import detect_service_unavailability
from incident_agent.anomaly_detection.common import DetectorThresholds, SeriesPoint
from incident_agent.anomaly_detection.cpu import detect_cpu_anomalies
from incident_agent.anomaly_detection.error_rate import detect_error_rate_spikes
from incident_agent.anomaly_detection.latency import detect_latency_spikes
from incident_agent.anomaly_detection.memory import detect_memory_anomalies
from incident_agent.anomaly_detection.traffic import detect_traffic_drops
from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.schemas.anomaly import AnomalyDetectionResult
from incident_agent.schemas.timeline import TimelineAlignmentResult, TimelineEvent


class AnomalyDetectionConfig(BaseModel):
    """Configurable thresholds for all detector modules."""

    error_rate: DetectorThresholds = Field(default_factory=DetectorThresholds)
    latency: DetectorThresholds = Field(default_factory=DetectorThresholds)
    cpu: DetectorThresholds = Field(default_factory=DetectorThresholds)
    memory: DetectorThresholds = Field(default_factory=DetectorThresholds)
    traffic: DetectorThresholds = Field(
        default_factory=lambda: DetectorThresholds(
            z_threshold=2.5,
            mad_multiplier=2.5,
            min_relative_change=0.15,
        )
    )
    availability: DetectorThresholds = Field(default_factory=DetectorThresholds)


def load_anomaly_detection_config(
    path: str | Path = "configs/default.yaml",
) -> AnomalyDetectionConfig:
    """Load anomaly thresholds from YAML."""

    loaded = load_settings_from_yaml(Path(path))
    section = loaded.get("anomaly_detection", {})
    if not isinstance(section, dict):
        raise ValueError("The 'anomaly_detection' section must be a mapping.")
    return AnomalyDetectionConfig.model_validate(section)


def detect_anomalies(
    alignment: TimelineAlignmentResult,
    *,
    bucket_size_minutes: int,
    config: AnomalyDetectionConfig,
) -> AnomalyDetectionResult:
    """Run all detectors across service-level and global signals."""

    anomalies = []

    latency_points = _build_points(
        alignment.events,
        metric_kind="latency",
        agg="p95",
        bucket_size_minutes=bucket_size_minutes,
    )
    anomalies.extend(detect_latency_spikes(latency_points, thresholds=config.latency))

    cpu_points = _build_points(
        alignment.events,
        metric_kind="cpu",
        agg="mean",
        bucket_size_minutes=bucket_size_minutes,
    )
    anomalies.extend(detect_cpu_anomalies(cpu_points, thresholds=config.cpu))

    memory_points = _build_points(
        alignment.events,
        metric_kind="memory",
        agg="mean",
        bucket_size_minutes=bucket_size_minutes,
    )
    anomalies.extend(detect_memory_anomalies(memory_points, thresholds=config.memory))

    error_rate_points = _build_points(
        alignment.events,
        metric_kind="error_rate",
        agg="mean",
        bucket_size_minutes=bucket_size_minutes,
    )
    anomalies.extend(detect_error_rate_spikes(error_rate_points, thresholds=config.error_rate))

    traffic_points = _build_points(
        alignment.events,
        metric_kind="traffic",
        agg="sum",
        bucket_size_minutes=bucket_size_minutes,
    )
    anomalies.extend(detect_traffic_drops(traffic_points, thresholds=config.traffic))

    availability_points = _build_points(
        alignment.events,
        metric_kind="availability",
        agg="sum",
        bucket_size_minutes=bucket_size_minutes,
    )
    anomalies.extend(
        detect_service_unavailability(
            availability_points,
            thresholds=config.availability,
        )
    )

    ordered = sorted(
        anomalies,
        key=lambda item: (
            item.timestamp_window_start,
            item.affected_service,
            item.anomaly_type,
        ),
    )
    return AnomalyDetectionResult(anomalies=ordered)


def _build_points(
    events: list[TimelineEvent],
    *,
    metric_kind: str,
    agg: str,
    bucket_size_minutes: int,
) -> list[SeriesPoint]:
    service_values: dict[tuple[datetime, str], list[float]] = defaultdict(list)
    global_values: dict[datetime, list[float]] = defaultdict(list)

    for event in events:
        value = _extract_metric_value(event, metric_kind=metric_kind)
        if value is None:
            continue
        service_key = (event.bucket_start, event.service)
        service_values[service_key].append(value)
        global_values[event.bucket_start].append(value)

    points: list[SeriesPoint] = []
    sorted_service_values = sorted(
        service_values.items(),
        key=lambda item: (item[0][0], item[0][1]),
    )
    for (bucket_start, service), values in sorted_service_values:
        points.append(
            SeriesPoint(
                bucket_start=bucket_start,
                bucket_end=bucket_start + timedelta(minutes=bucket_size_minutes),
                service=service,
                value=_aggregate(values, agg),
                scope="service",
            )
        )

    for bucket_start, values in sorted(global_values.items(), key=lambda item: item[0]):
        points.append(
            SeriesPoint(
                bucket_start=bucket_start,
                bucket_end=bucket_start + timedelta(minutes=bucket_size_minutes),
                service="global",
                value=_aggregate(values, agg),
                scope="global",
            )
        )
    return points


def _extract_metric_value(event: TimelineEvent, *, metric_kind: str) -> float | None:
    metric_name = (event.metric_name or "").lower()
    message = (event.message or "").lower()

    if metric_kind == "latency":
        if event.signal == "latency":
            return event.value
        return None

    if metric_kind == "cpu":
        if event.signal == "cpu":
            return event.value
        return None

    if metric_kind == "memory":
        if event.signal == "memory":
            return event.value
        return None

    if metric_kind == "error_rate":
        if "error_rate" in metric_name and event.value is not None:
            return event.value
        if event.source == "log" and event.severity in {"ERROR", "CRITICAL"}:
            return 1.0
        return None

    if metric_kind == "traffic":
        if any(
            name in metric_name
            for name in ["request_count", "traffic", "throughput", "rps"]
        ):
            return event.value
        return None

    if metric_kind == "availability":
        if "service_unavailable" in metric_name or "failure_rate" in metric_name:
            return event.value
        if event.source == "log" and any(
            token in message for token in ["unavailable", "outage", "down"]
        ):
            return 1.0
        return None

    return None


def _aggregate(values: list[float], mode: str) -> float:
    if mode == "sum":
        return float(sum(values))
    if mode == "p95":
        ordered = sorted(values)
        rank = round(0.95 * (len(ordered) - 1))
        return float(ordered[rank])
    return float(mean(values))
