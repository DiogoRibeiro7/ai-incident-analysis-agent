from __future__ import annotations

from datetime import UTC, datetime, timedelta

from incident_agent.correlation.graph import ServiceDependencyGraph, ServiceRelations
from incident_agent.rca.engine import RCAConfig, perform_rca
from incident_agent.schemas.anomaly import AnomalyCandidate, AnomalyType
from incident_agent.schemas.incident import CorrelatedIncidentCandidate
from incident_agent.schemas.rca import RootCauseHypothesis


def _anomaly(
    *,
    service: str,
    anomaly_type: AnomalyType,
    severity: float,
    minute: int,
) -> AnomalyCandidate:
    start = datetime(2026, 3, 20, 11, minute, tzinfo=UTC)
    return AnomalyCandidate(
        timestamp_window_start=start,
        timestamp_window_end=start + timedelta(minutes=5),
        anomaly_type=anomaly_type,
        affected_service=service,
        severity_score=severity,
        observed_value=10.0,
        baseline_value=1.0,
        evidence_summary="evidence",
        scope="service",
    )


def _graph() -> ServiceDependencyGraph:
    return ServiceDependencyGraph(
        services={
            "api-service": ServiceRelations(upstream=["orders-db"], downstream=["gateway-service"]),
            "gateway-service": ServiceRelations(upstream=["api-service"], downstream=[]),
            "orders-db": ServiceRelations(upstream=[], downstream=["api-service"]),
        }
    )


def test_perform_rca_returns_expected_artifacts() -> None:
    incident = CorrelatedIncidentCandidate(
        incident_id="inc-1",
        start_time=datetime(2026, 3, 20, 11, 0, tzinfo=UTC),
        end_time=datetime(2026, 3, 20, 11, 5, tzinfo=UTC),
        impacted_services=["api-service", "gateway-service"],
        suspected_primary_service="api-service",
        evidence=[
            _anomaly(
                service="api-service",
                anomaly_type="service_unavailability",
                severity=8.0,
                minute=0,
            ),
            _anomaly(
                service="gateway-service",
                anomaly_type="traffic_drop",
                severity=5.0,
                minute=1,
            ),
        ],
        correlation_score=7.5,
    )

    result = perform_rca(
        [incident],
        config=RCAConfig(service_failure_bonus=1.0, downstream_bonus=1.0, ambiguity_delta=0.2),
        dependency_graph=_graph(),
    )

    assert len(result.bundles) == 1
    assert len(result.summaries) == 1
    assert len(result.hypotheses) == 1
    hypothesis = result.hypotheses[0]
    assert hypothesis.suspected_root_cause_service == "api-service"
    assert "gateway-service" in hypothesis.impacted_downstream_services
    assert hypothesis.root_cause_support > 0
    assert "root_cause_support" in hypothesis.model_dump()
    assert "confidence_score" not in hypothesis.model_dump()


def test_root_cause_hypothesis_accepts_legacy_confidence_score() -> None:
    hypothesis = RootCauseHypothesis.model_validate(
        {
            "incident_id": "inc-legacy",
            "suspected_root_cause_service": "api-service",
            "confidence_score": 0.42,
            "contributing_signals": [],
            "impacted_downstream_services": [],
            "unresolved_ambiguities": [],
            "rationale": "legacy artifact",
        }
    )

    assert hypothesis.root_cause_support == 0.42
    assert hypothesis.confidence_score == 0.42


def test_perform_rca_marks_ambiguity_when_scores_are_close() -> None:
    incident = CorrelatedIncidentCandidate(
        incident_id="inc-2",
        start_time=datetime(2026, 3, 20, 11, 0, tzinfo=UTC),
        end_time=datetime(2026, 3, 20, 11, 5, tzinfo=UTC),
        impacted_services=["api-service", "gateway-service"],
        suspected_primary_service="api-service",
        evidence=[
            _anomaly(
                service="api-service",
                anomaly_type="latency_spike",
                severity=6.0,
                minute=0,
            ),
            _anomaly(
                service="gateway-service",
                anomaly_type="latency_spike",
                severity=6.0,
                minute=1,
            ),
        ],
        correlation_score=6.0,
    )

    result = perform_rca(
        [incident],
        config=RCAConfig(service_failure_bonus=0.0, downstream_bonus=0.0, ambiguity_delta=1.0),
        dependency_graph=_graph(),
    )

    assert result.hypotheses[0].unresolved_ambiguities
