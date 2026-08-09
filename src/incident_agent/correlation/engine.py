"""Correlation engine that groups anomaly candidates into incidents."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.correlation.graph import ServiceDependencyGraph, load_service_dependency_graph
from incident_agent.schemas.anomaly import AnomalyCandidate
from incident_agent.schemas.incident import CorrelatedIncidentCandidate, IncidentCorrelationResult


class CorrelationConfig(BaseModel):
    """Configuration for anomaly correlation and root-cause ranking."""

    max_time_distance_minutes: int = 10
    minimum_evidence_count: int = 2
    severity_weighting: dict[str, float] = Field(
        default_factory=lambda: {
            "error_rate_spike": 1.1,
            "latency_spike": 1.0,
            "cpu_anomaly": 0.9,
            "memory_anomaly": 0.9,
            "traffic_drop": 1.0,
            "service_unavailability": 1.2,
            "error_log_burst": 1.0,
            "critical_log_burst": 1.2,
        }
    )
    dependency_downstream_bonus: float = 1.0
    dependency_upstream_penalty: float = 0.5
    cross_signal_bonus: float = 0.3
    same_service_bonus: float = 0.4
    dependency_graph_path: str = "configs/service_dependencies.yaml"


def load_correlation_config(path: str | Path = "configs/default.yaml") -> CorrelationConfig:
    """Load correlation config from YAML."""

    loaded = load_settings_from_yaml(Path(path))
    section = loaded.get("correlation", {})
    if not isinstance(section, dict):
        raise ValueError("The 'correlation' section must be a mapping.")
    return CorrelationConfig.model_validate(section)


def correlate_anomalies(
    anomalies: list[AnomalyCandidate],
    *,
    config: CorrelationConfig,
    dependency_graph: ServiceDependencyGraph,
) -> IncidentCorrelationResult:
    """Group anomaly candidates into incident candidates with dependency-aware ranking."""

    if not anomalies:
        return IncidentCorrelationResult()

    ordered = sorted(
        anomalies,
        key=lambda item: (
            item.timestamp_window_start,
            item.timestamp_window_end,
            item.affected_service,
            item.anomaly_type,
        ),
    )

    clusters: list[list[AnomalyCandidate]] = []
    for anomaly in ordered:
        matching_indexes = [
            index
            for index, cluster in enumerate(clusters)
            if _is_related(anomaly, cluster, config, dependency_graph)
        ]
        if not matching_indexes:
            clusters.append([anomaly])
            continue

        first_index = matching_indexes[0]
        clusters[first_index].append(anomaly)
        for extra_index in reversed(matching_indexes[1:]):
            clusters[first_index].extend(clusters.pop(extra_index))

    incidents: list[CorrelatedIncidentCandidate] = []
    for cluster in clusters:
        if len(cluster) < config.minimum_evidence_count:
            continue

        evidence = sorted(
            cluster,
            key=lambda item: (
                item.timestamp_window_start,
                item.affected_service,
                item.anomaly_type,
            ),
        )
        start_time = min(item.timestamp_window_start for item in evidence)
        end_time = max(item.timestamp_window_end for item in evidence)
        impacted_services = sorted(
            {item.affected_service for item in evidence if item.affected_service != "global"}
        )
        if not impacted_services:
            impacted_services = ["global"]

        suspected_primary_service, root_score = _rank_primary_service(
            evidence=evidence,
            impacted_services=set(impacted_services),
            config=config,
            dependency_graph=dependency_graph,
        )
        correlation_score = _compute_correlation_score(
            evidence=evidence,
            config=config,
            root_score=root_score,
        )

        incidents.append(
            CorrelatedIncidentCandidate(
                incident_id=_incident_id(start_time, len(incidents) + 1),
                start_time=start_time,
                end_time=end_time,
                impacted_services=impacted_services,
                suspected_primary_service=suspected_primary_service,
                evidence=evidence,
                correlation_score=round(correlation_score, 4),
            )
        )

    ordered_incidents = sorted(
        incidents,
        key=lambda item: (item.start_time, item.end_time, item.incident_id),
    )
    return IncidentCorrelationResult(incidents=ordered_incidents)


def load_dependency_graph_for_correlation(config: CorrelationConfig) -> ServiceDependencyGraph:
    """Load dependency graph from config path."""

    return load_service_dependency_graph(config.dependency_graph_path)


def _is_related(
    anomaly: AnomalyCandidate,
    cluster: list[AnomalyCandidate],
    config: CorrelationConfig,
    dependency_graph: ServiceDependencyGraph,
) -> bool:
    for existing in cluster:
        if not _is_temporally_close(existing, anomaly, config.max_time_distance_minutes):
            continue

        same_service = (
            anomaly.affected_service == existing.affected_service
            and anomaly.affected_service != "global"
        )
        dependency_related = (
            anomaly.affected_service != "global"
            and existing.affected_service != "global"
            and dependency_graph.are_related(anomaly.affected_service, existing.affected_service)
        )
        same_family = anomaly.anomaly_type == existing.anomaly_type
        cross_signal = (
            anomaly.affected_service == existing.affected_service
            and anomaly.anomaly_type != existing.anomaly_type
        )
        if same_service or dependency_related or same_family or cross_signal:
            return True
    return False


def _is_temporally_close(
    first: AnomalyCandidate,
    second: AnomalyCandidate,
    max_time_distance_minutes: int,
) -> bool:
    threshold = timedelta(minutes=max_time_distance_minutes)
    window_gap = max(
        timedelta(0),
        max(
            second.timestamp_window_start - first.timestamp_window_end,
            first.timestamp_window_start - second.timestamp_window_end,
        ),
    )
    return window_gap <= threshold


def _rank_primary_service(
    *,
    evidence: list[AnomalyCandidate],
    impacted_services: set[str],
    config: CorrelationConfig,
    dependency_graph: ServiceDependencyGraph,
) -> tuple[str, float]:
    scores: dict[str, float] = {service: 0.0 for service in impacted_services}
    for anomaly in evidence:
        service = anomaly.affected_service
        if service not in scores:
            continue
        weight = config.severity_weighting.get(anomaly.anomaly_type, 1.0)
        scores[service] += anomaly.severity_score * weight

    for service in scores:
        scores[service] += (
            dependency_graph.downstream_impacted_count(service, impacted_services)
            * config.dependency_downstream_bonus
        )
        scores[service] -= (
            dependency_graph.upstream_impacted_count(service, impacted_services)
            * config.dependency_upstream_penalty
        )

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ordered[0]


def _compute_correlation_score(
    *,
    evidence: list[AnomalyCandidate],
    config: CorrelationConfig,
    root_score: float,
) -> float:
    average_severity = sum(item.severity_score for item in evidence) / len(evidence)
    anomaly_types = {item.anomaly_type for item in evidence}
    services = {item.affected_service for item in evidence}
    cross_signal_bonus = config.cross_signal_bonus if len(anomaly_types) > 1 else 0.0
    same_service_bonus = config.same_service_bonus if len(services) == 1 else 0.0
    evidence_bonus = min(3.0, len(evidence) * 0.2)
    return (
        average_severity
        + root_score * 0.1
        + cross_signal_bonus
        + same_service_bonus
        + evidence_bonus
    )


def _incident_id(start_time: datetime, index: int) -> str:
    suffix = start_time.strftime("%Y%m%dT%H%M%SZ")
    return f"inc-{suffix}-{index:03d}"
