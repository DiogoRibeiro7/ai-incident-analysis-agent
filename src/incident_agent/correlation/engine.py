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
    relationship_threshold: float = 1.0
    temporal_weight: float = 0.4
    same_service_weight: float = 1.0
    dependency_weight: float = 0.8
    cross_signal_weight: float = 0.5
    same_family_weight: float = 0.2
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
        matching_index = _best_cluster_index(
            anomaly=anomaly,
            clusters=clusters,
            config=config,
            dependency_graph=dependency_graph,
        )
        if matching_index is None:
            clusters.append([anomaly])
            continue

        clusters[matching_index].append(anomaly)

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


def _best_cluster_index(
    *,
    anomaly: AnomalyCandidate,
    clusters: list[list[AnomalyCandidate]],
    config: CorrelationConfig,
    dependency_graph: ServiceDependencyGraph,
) -> int | None:
    scored_matches: list[tuple[float, int]] = []
    for index, cluster in enumerate(clusters):
        pair_scores = [
            _relationship_score(
                first=existing,
                second=anomaly,
                config=config,
                dependency_graph=dependency_graph,
            )
            for existing in cluster
        ]
        if (
            not pair_scores
            or max(pair_scores) < config.relationship_threshold
            or not _cluster_supports_candidate(
                anomaly=anomaly,
                cluster=cluster,
                config=config,
                dependency_graph=dependency_graph,
            )
        ):
            continue
        scored_matches.append((max(pair_scores), index))

    if not scored_matches:
        return None
    return sorted(scored_matches, key=lambda item: (-item[0], item[1]))[0][1]


def _relationship_score(
    *,
    first: AnomalyCandidate,
    second: AnomalyCandidate,
    config: CorrelationConfig,
    dependency_graph: ServiceDependencyGraph,
) -> float:
    time_score = _temporal_score(
        first,
        second,
        config.max_time_distance_minutes,
    )
    if time_score <= 0.0:
        return 0.0

    same_service = (
        first.affected_service == second.affected_service and first.affected_service != "global"
    )
    dependency_related = (
        first.affected_service != "global"
        and second.affected_service != "global"
        and dependency_graph.are_related(first.affected_service, second.affected_service)
    )
    cross_signal = same_service and first.anomaly_type != second.anomaly_type
    same_family = first.anomaly_type == second.anomaly_type

    return (config.temporal_weight * time_score) + _structural_score(
        same_service=same_service,
        dependency_related=dependency_related,
        cross_signal=cross_signal,
        same_family=same_family,
        config=config,
    )


def _cluster_supports_candidate(
    *,
    anomaly: AnomalyCandidate,
    cluster: list[AnomalyCandidate],
    config: CorrelationConfig,
    dependency_graph: ServiceDependencyGraph,
) -> bool:
    candidate_service = anomaly.affected_service
    cluster_services = {
        existing.affected_service for existing in cluster if existing.affected_service != "global"
    }

    if len(cluster_services) <= 1 or candidate_service in cluster_services:
        return True

    if candidate_service != "global" and all(
        dependency_graph.are_related(candidate_service, service) for service in cluster_services
    ):
        return True

    return _has_cross_signal_support([*cluster, anomaly]) and any(
        candidate_service != "global"
        and existing.affected_service != "global"
        and dependency_graph.are_related(candidate_service, existing.affected_service)
        for existing in cluster
    )


def _has_cross_signal_support(anomalies: list[AnomalyCandidate]) -> bool:
    return len({anomaly.anomaly_type for anomaly in anomalies}) > 1


def _structural_score(
    *,
    same_service: bool,
    dependency_related: bool,
    cross_signal: bool,
    same_family: bool,
    config: CorrelationConfig,
) -> float:
    return (
        (config.same_service_weight if same_service else 0.0)
        + (config.dependency_weight if dependency_related else 0.0)
        + (config.cross_signal_weight if cross_signal else 0.0)
        + (config.same_family_weight if same_family else 0.0)
    )


def _temporal_score(
    first: AnomalyCandidate,
    second: AnomalyCandidate,
    max_time_distance_minutes: int,
) -> float:
    threshold = timedelta(minutes=max_time_distance_minutes)
    window_gap = _window_gap(first, second)
    if window_gap > threshold:
        return 0.0
    if threshold.total_seconds() <= 0:
        return 1.0 if window_gap == timedelta(0) else 0.0
    return 1.0 - (window_gap.total_seconds() / threshold.total_seconds())


def _is_temporally_close(
    first: AnomalyCandidate,
    second: AnomalyCandidate,
    max_time_distance_minutes: int,
) -> bool:
    return _temporal_score(first, second, max_time_distance_minutes) > 0.0


def _window_gap(first: AnomalyCandidate, second: AnomalyCandidate) -> timedelta:
    return max(
        timedelta(0),
        max(
            second.timestamp_window_start - first.timestamp_window_end,
            first.timestamp_window_start - second.timestamp_window_end,
        ),
    )


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
