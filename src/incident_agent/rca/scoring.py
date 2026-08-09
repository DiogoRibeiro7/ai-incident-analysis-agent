"""Root-cause scoring for RCA."""

from __future__ import annotations

from incident_agent.correlation.graph import ServiceDependencyGraph
from incident_agent.schemas.anomaly import AnomalyCandidate


def score_root_candidates(
    *,
    evidence: list[AnomalyCandidate],
    impacted_services: list[str],
    dependency_graph: ServiceDependencyGraph,
    service_failure_bonus: float,
    downstream_bonus: float,
    ambiguity_delta: float,
) -> tuple[str, float, list[str]]:
    """Rank candidate root services and return top service, confidence, ambiguities."""

    candidates = [service for service in impacted_services if service != "global"]
    if not candidates:
        return "global", 0.0, []

    scores: dict[str, float] = {service: 0.0 for service in candidates}
    for anomaly in evidence:
        service = anomaly.affected_service
        if service not in scores:
            continue
        score = anomaly.severity_score
        if anomaly.anomaly_type in {
            "service_unavailability",
            "error_rate_spike",
            "error_log_burst",
            "critical_log_burst",
        }:
            score += service_failure_bonus
        scores[service] += score

    impacted_set = set(impacted_services)
    for service in scores:
        downstream_count = dependency_graph.downstream_impacted_count(service, impacted_set)
        scores[service] += downstream_count * downstream_bonus

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_service, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    confidence = top_score / max(sum(scores.values()), 1e-6)
    ambiguities: list[str] = []
    if len(ordered) > 1 and abs(top_score - second_score) <= ambiguity_delta:
        ambiguities.append(
            f"Top root-cause candidates are close: {ordered[0][0]} ({top_score:.2f}) "
            f"vs {ordered[1][0]} ({second_score:.2f})."
        )
    return top_service, min(confidence, 1.0), ambiguities
