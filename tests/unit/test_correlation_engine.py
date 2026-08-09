from __future__ import annotations

from datetime import UTC, datetime, timedelta

from incident_agent.correlation.engine import CorrelationConfig, correlate_anomalies
from incident_agent.correlation.graph import ServiceDependencyGraph, ServiceRelations
from incident_agent.schemas.anomaly import AnomalyCandidate, AnomalyType


def _anomaly(
    *,
    minute: int,
    service: str,
    anomaly_type: AnomalyType,
    severity: float = 6.0,
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
        evidence_summary="synthetic evidence",
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


def test_single_service_incident_grouping() -> None:
    anomalies = [
        _anomaly(minute=0, service="api-service", anomaly_type="latency_spike"),
        _anomaly(minute=2, service="api-service", anomaly_type="error_rate_spike"),
    ]
    config = CorrelationConfig(max_time_distance_minutes=10, minimum_evidence_count=2)

    result = correlate_anomalies(anomalies, config=config, dependency_graph=_graph())

    assert len(result.incidents) == 1
    incident = result.incidents[0]
    assert incident.impacted_services == ["api-service"]
    assert incident.suspected_primary_service == "api-service"
    assert len(incident.evidence) == 2


def test_multi_service_incident_grouping() -> None:
    anomalies = [
        _anomaly(minute=0, service="api-service", anomaly_type="service_unavailability"),
        _anomaly(minute=3, service="gateway-service", anomaly_type="traffic_drop"),
    ]
    config = CorrelationConfig(max_time_distance_minutes=10, minimum_evidence_count=2)

    result = correlate_anomalies(anomalies, config=config, dependency_graph=_graph())

    assert len(result.incidents) == 1
    incident = result.incidents[0]
    assert incident.impacted_services == ["api-service", "gateway-service"]


def test_unrelated_same_family_anomalies_do_not_group() -> None:
    anomalies = [
        _anomaly(minute=0, service="api-service", anomaly_type="cpu_anomaly"),
        _anomaly(minute=0, service="worker-service", anomaly_type="cpu_anomaly"),
    ]
    config = CorrelationConfig(max_time_distance_minutes=10, minimum_evidence_count=1)

    result = correlate_anomalies(anomalies, config=config, dependency_graph=_graph())

    assert len(result.incidents) == 2
    assert [incident.impacted_services for incident in result.incidents] == [
        ["api-service"],
        ["worker-service"],
    ]


def test_same_service_cross_signal_anomalies_group() -> None:
    anomalies = [
        _anomaly(minute=0, service="api-service", anomaly_type="latency_spike"),
        _anomaly(minute=1, service="api-service", anomaly_type="error_rate_spike"),
    ]
    config = CorrelationConfig(max_time_distance_minutes=10, minimum_evidence_count=2)

    result = correlate_anomalies(anomalies, config=config, dependency_graph=_graph())

    assert len(result.incidents) == 1
    assert result.incidents[0].impacted_services == ["api-service"]


def test_false_grouping_prevention_by_time_gap() -> None:
    anomalies = [
        _anomaly(minute=0, service="api-service", anomaly_type="latency_spike"),
        _anomaly(minute=1, service="api-service", anomaly_type="error_rate_spike"),
        _anomaly(minute=50, service="api-service", anomaly_type="latency_spike"),
        _anomaly(minute=51, service="api-service", anomaly_type="error_rate_spike"),
    ]
    config = CorrelationConfig(max_time_distance_minutes=10, minimum_evidence_count=2)

    result = correlate_anomalies(anomalies, config=config, dependency_graph=_graph())

    assert len(result.incidents) == 2
    assert result.incidents[0].end_time < result.incidents[1].start_time


def test_weak_dependency_chain_does_not_create_mega_cluster() -> None:
    graph = ServiceDependencyGraph(
        services={
            "service-a": ServiceRelations(upstream=[], downstream=["service-b"]),
            "service-b": ServiceRelations(upstream=["service-a"], downstream=["service-c"]),
            "service-c": ServiceRelations(upstream=["service-b"], downstream=[]),
        }
    )
    anomalies = [
        _anomaly(minute=0, service="service-a", anomaly_type="latency_spike"),
        _anomaly(minute=0, service="service-b", anomaly_type="latency_spike"),
        _anomaly(minute=0, service="service-c", anomaly_type="latency_spike"),
    ]
    config = CorrelationConfig(max_time_distance_minutes=10, minimum_evidence_count=1)

    result = correlate_anomalies(anomalies, config=config, dependency_graph=graph)

    assert len(result.incidents) == 2
    assert result.incidents[0].impacted_services == ["service-a", "service-b"]
    assert result.incidents[1].impacted_services == ["service-c"]


def test_dependency_aware_primary_service_ranking() -> None:
    anomalies = [
        _anomaly(
            minute=0,
            service="api-service",
            anomaly_type="service_unavailability",
            severity=5.0,
        ),
        _anomaly(
            minute=1,
            service="gateway-service",
            anomaly_type="service_unavailability",
            severity=5.0,
        ),
    ]
    config = CorrelationConfig(
        max_time_distance_minutes=10,
        minimum_evidence_count=2,
        dependency_downstream_bonus=2.0,
        dependency_upstream_penalty=0.0,
    )

    result = correlate_anomalies(anomalies, config=config, dependency_graph=_graph())

    assert len(result.incidents) == 1
    assert result.incidents[0].suspected_primary_service == "api-service"
