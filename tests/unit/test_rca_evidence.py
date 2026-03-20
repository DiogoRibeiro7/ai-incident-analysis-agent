from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from incident_agent.rca.evidence import extract_contributing_signals, rank_evidence
from incident_agent.schemas.anomaly import AnomalyCandidate, AnomalyType


def _anomaly(
    *,
    anomaly_type: AnomalyType,
    severity: float,
    scope: Literal["service", "global"] = "service",
) -> AnomalyCandidate:
    start = datetime(2026, 3, 20, 11, 0, tzinfo=UTC)
    return AnomalyCandidate(
        timestamp_window_start=start,
        timestamp_window_end=start + timedelta(minutes=5),
        anomaly_type=anomaly_type,
        affected_service="api-service" if scope == "service" else "global",
        severity_score=severity,
        observed_value=10.0,
        baseline_value=1.0,
        evidence_summary="evidence",
        scope=scope,
    )


def test_rank_evidence_prioritizes_severity_and_service_scope() -> None:
    evidence = [
        _anomaly(anomaly_type="latency_spike", severity=5.0, scope="global"),
        _anomaly(anomaly_type="cpu_anomaly", severity=8.0, scope="service"),
        _anomaly(anomaly_type="error_rate_spike", severity=8.0, scope="global"),
    ]

    ranked = rank_evidence(evidence)

    assert ranked[0].anomaly_type == "cpu_anomaly"
    assert ranked[1].anomaly_type == "error_rate_spike"


def test_extract_contributing_signals_keeps_order_without_duplicates() -> None:
    evidence = [
        _anomaly(anomaly_type="latency_spike", severity=5.0),
        _anomaly(anomaly_type="latency_spike", severity=4.0),
        _anomaly(anomaly_type="cpu_anomaly", severity=3.0),
    ]

    signals = extract_contributing_signals(evidence)

    assert signals == ["latency_spike", "cpu_anomaly"]
