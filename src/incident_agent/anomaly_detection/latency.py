"""Latency spike detector."""

from __future__ import annotations

from incident_agent.anomaly_detection.common import (
    DetectorThresholds,
    SeriesPoint,
    detect_series_anomalies,
)
from incident_agent.schemas.anomaly import AnomalyCandidate


def detect_latency_spikes(
    points: list[SeriesPoint],
    *,
    thresholds: DetectorThresholds,
) -> list[AnomalyCandidate]:
    """Detect latency spikes using robust rolling baselines."""

    return detect_series_anomalies(
        points=points,
        anomaly_type="latency_spike",
        direction="spike",
        thresholds=thresholds,
    )
