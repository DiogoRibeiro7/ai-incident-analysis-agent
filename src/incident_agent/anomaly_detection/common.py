"""Common utilities for detector modules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Literal

from pydantic import BaseModel

from incident_agent.schemas.anomaly import AnomalyCandidate, AnomalyType

Direction = Literal["spike", "drop"]


class DetectorThresholds(BaseModel):
    """Thresholds used by rule-based detectors."""

    min_support: int = 5
    lookback_windows: int = 20
    z_threshold: float = 3.0
    mad_multiplier: float = 3.0
    min_relative_change: float = 0.2


@dataclass(frozen=True)
class SeriesPoint:
    """A single time-series point to evaluate for anomalies."""

    bucket_start: datetime
    bucket_end: datetime
    service: str
    value: float
    scope: Literal["service", "global"]


def group_points_by_service(points: list[SeriesPoint]) -> dict[str, list[SeriesPoint]]:
    """Group points by service while preserving chronological order."""

    grouped: dict[str, list[SeriesPoint]] = defaultdict(list)
    for point in points:
        grouped[point.service].append(point)
    for service in grouped:
        grouped[service] = sorted(grouped[service], key=lambda item: item.bucket_start)
    return dict(grouped)


def detect_series_anomalies(
    *,
    points: list[SeriesPoint],
    anomaly_type: AnomalyType,
    direction: Direction,
    thresholds: DetectorThresholds,
) -> list[AnomalyCandidate]:
    """Detect anomalies in grouped service/global series with rolling robust baselines."""

    anomalies: list[AnomalyCandidate] = []
    grouped = group_points_by_service(points)
    for service, service_points in grouped.items():
        for index, point in enumerate(service_points):
            history = [
                previous.value
                for previous in service_points[max(0, index - thresholds.lookback_windows) : index]
            ]
            if len(history) < thresholds.min_support:
                continue

            baseline = median(history)
            abs_deviations = [abs(value - baseline) for value in history]
            mad = median(abs_deviations)
            robust_scale = max(1.4826 * mad, 1e-6)
            z_score = (point.value - baseline) / robust_scale

            if not _passes_direction(
                direction=direction,
                z_score=z_score,
                threshold=thresholds.z_threshold,
            ):
                continue
            if not _passes_mad_rule(
                value=point.value,
                baseline=baseline,
                robust_scale=robust_scale,
                direction=direction,
                multiplier=thresholds.mad_multiplier,
            ):
                continue
            if not _passes_relative_change(
                value=point.value,
                baseline=baseline,
                direction=direction,
                min_relative_change=thresholds.min_relative_change,
            ):
                continue

            severity = min(10.0, abs(z_score))
            anomalies.append(
                AnomalyCandidate(
                    timestamp_window_start=point.bucket_start,
                    timestamp_window_end=point.bucket_end,
                    anomaly_type=anomaly_type,
                    affected_service=service,
                    severity_score=severity,
                    observed_value=point.value,
                    baseline_value=baseline,
                    evidence_summary=(
                        f"Observed={point.value:.3f}, baseline={baseline:.3f}, "
                        f"z={z_score:.2f}, mad_scale={robust_scale:.3f}"
                    ),
                    scope=point.scope,
                )
            )

    return sorted(
        anomalies,
        key=lambda item: (
            item.timestamp_window_start,
            item.affected_service,
            item.anomaly_type,
        ),
    )


def _passes_direction(*, direction: Direction, z_score: float, threshold: float) -> bool:
    if direction == "spike":
        return z_score >= threshold
    return z_score <= -threshold


def _passes_mad_rule(
    *,
    value: float,
    baseline: float,
    robust_scale: float,
    direction: Direction,
    multiplier: float,
) -> bool:
    if direction == "spike":
        return value > baseline + (multiplier * robust_scale)
    return value < baseline - (multiplier * robust_scale)


def _passes_relative_change(
    *,
    value: float,
    baseline: float,
    direction: Direction,
    min_relative_change: float,
) -> bool:
    floor = max(abs(baseline), 1e-6)
    relative_change = abs(value - baseline) / floor
    if relative_change < min_relative_change:
        return False

    if direction == "spike":
        return value > baseline
    return value < baseline
