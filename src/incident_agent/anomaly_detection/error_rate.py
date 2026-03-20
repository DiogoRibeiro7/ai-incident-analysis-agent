"""Error-rate spike detector."""

from __future__ import annotations

from incident_agent.anomaly_detection.common import (
    DetectorThresholds,
    SeriesPoint,
    detect_series_anomalies,
)
from incident_agent.schemas.anomaly import AnomalyCandidate


def detect_error_rate_spikes(
    points: list[SeriesPoint],
    *,
    thresholds: DetectorThresholds,
) -> list[AnomalyCandidate]:
    """Detect error-rate spikes using robust rolling baselines."""

    return detect_series_anomalies(
        points=points,
        anomaly_type="error_rate_spike",
        direction="spike",
        thresholds=thresholds,
    )
