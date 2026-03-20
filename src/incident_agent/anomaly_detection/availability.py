"""Service unavailability detector."""

from __future__ import annotations

from incident_agent.anomaly_detection.common import (
    DetectorThresholds,
    SeriesPoint,
    detect_series_anomalies,
)
from incident_agent.schemas.anomaly import AnomalyCandidate


def detect_service_unavailability(
    points: list[SeriesPoint],
    *,
    thresholds: DetectorThresholds,
) -> list[AnomalyCandidate]:
    """Detect service unavailability signal spikes using robust baselines."""

    return detect_series_anomalies(
        points=points,
        anomaly_type="service_unavailability",
        direction="spike",
        thresholds=thresholds,
    )
