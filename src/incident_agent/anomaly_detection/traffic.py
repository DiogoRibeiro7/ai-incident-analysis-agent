"""Traffic drop detector."""

from __future__ import annotations

from incident_agent.anomaly_detection.common import (
    DetectorThresholds,
    SeriesPoint,
    detect_series_anomalies,
)
from incident_agent.schemas.anomaly import AnomalyCandidate


def detect_traffic_drops(
    points: list[SeriesPoint],
    *,
    thresholds: DetectorThresholds,
) -> list[AnomalyCandidate]:
    """Detect traffic drops using robust rolling baselines."""

    return detect_series_anomalies(
        points=points,
        anomaly_type="traffic_drop",
        direction="drop",
        thresholds=thresholds,
    )
