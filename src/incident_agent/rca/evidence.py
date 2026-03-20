"""Evidence ranking helpers for RCA."""

from __future__ import annotations

from incident_agent.schemas.anomaly import AnomalyCandidate


def rank_evidence(evidence: list[AnomalyCandidate]) -> list[AnomalyCandidate]:
    """Rank evidence by severity and service-level relevance."""

    return sorted(
        evidence,
        key=lambda item: (
            -item.severity_score,
            0 if item.scope == "service" else 1,
            item.timestamp_window_start,
            item.anomaly_type,
        ),
    )


def extract_contributing_signals(evidence: list[AnomalyCandidate]) -> list[str]:
    """Return unique anomaly types ordered by first appearance in ranked evidence."""

    ordered_types: list[str] = []
    for item in evidence:
        if item.anomaly_type not in ordered_types:
            ordered_types.append(item.anomaly_type)
    return ordered_types
