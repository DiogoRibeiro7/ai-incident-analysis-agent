"""Incident summary feature extraction for RCA."""

from __future__ import annotations

from statistics import mean

from incident_agent.schemas.anomaly import AnomalyCandidate
from incident_agent.schemas.incident import CorrelatedIncidentCandidate
from incident_agent.schemas.rca import IncidentSummaryFeatures


def summarize_incident_features(
    incident: CorrelatedIncidentCandidate,
    ranked_evidence: list[AnomalyCandidate],
) -> IncidentSummaryFeatures:
    """Build structured incident summary features from correlated evidence."""

    anomaly_type_counts: dict[str, int] = {}
    service_evidence_counts: dict[str, int] = {}

    for item in ranked_evidence:
        anomaly_type_counts[item.anomaly_type] = anomaly_type_counts.get(item.anomaly_type, 0) + 1
        service_evidence_counts[item.affected_service] = (
            service_evidence_counts.get(item.affected_service, 0) + 1
        )

    severities = [item.severity_score for item in ranked_evidence]
    average_severity = mean(severities) if severities else 0.0
    peak_severity = max(severities) if severities else 0.0

    return IncidentSummaryFeatures(
        incident_id=incident.incident_id,
        total_evidence=len(ranked_evidence),
        impacted_services=incident.impacted_services,
        anomaly_type_counts=anomaly_type_counts,
        service_evidence_counts=service_evidence_counts,
        average_severity=round(average_severity, 4),
        peak_severity=round(peak_severity, 4),
    )
