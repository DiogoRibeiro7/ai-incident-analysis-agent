"""Memory anomaly detector."""

from __future__ import annotations

from incident_agent.anomaly_detection.common import (
    DetectorThresholds,
    SeriesPoint,
    detect_series_anomalies,
)
from incident_agent.schemas.anomaly import AnomalyCandidate


def detect_memory_anomalies(
    points: list[SeriesPoint],
    *,
    thresholds: DetectorThresholds,
) -> list[AnomalyCandidate]:
    """Detect memory spikes using robust rolling baselines."""

    return detect_series_anomalies(
        points=points,
        anomaly_type="memory_anomaly",
        direction="spike",
        thresholds=thresholds,
    )
