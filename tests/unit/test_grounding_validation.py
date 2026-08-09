from __future__ import annotations

from datetime import UTC, datetime, timedelta

from incident_agent.core.settings import GroundingConfig
from incident_agent.grounding.validate import build_claim_citations, validate_report_grounding
from incident_agent.knowledge.retrieval import RetrievedSnippet
from incident_agent.schemas.anomaly import AnomalyCandidate, AnomalyType
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.schemas.grounding import ClaimType, ClaimValidationStatus
from incident_agent.schemas.rca import EvidenceBundle, RootCauseHypothesis


def _anomaly(
    *,
    anomaly_type: AnomalyType,
    affected_service: str,
    evidence_summary: str,
    observed_value: float = 1800.0,
    baseline_value: float = 120.0,
) -> AnomalyCandidate:
    start = datetime(2026, 3, 20, 11, 15, tzinfo=UTC)
    return AnomalyCandidate(
        timestamp_window_start=start,
        timestamp_window_end=start + timedelta(minutes=5),
        anomaly_type=anomaly_type,
        affected_service=affected_service,
        severity_score=9.4,
        observed_value=observed_value,
        baseline_value=baseline_value,
        evidence_summary=evidence_summary,
        scope="service",
    )


def _context(
    evidence: list[AnomalyCandidate] | None = None,
) -> tuple[EvidenceBundle, RootCauseHypothesis]:
    ranked_evidence = evidence or [
        _anomaly(
            anomaly_type="latency_spike",
            affected_service="checkout-service",
            evidence_summary="checkout-service latency increased",
        )
    ]
    bundle = EvidenceBundle(
        incident_id="inc-1",
        ranked_evidence=ranked_evidence,
        contributing_signals=["latency_spike"],
        impacted_downstream_services=["api-service"],
        unresolved_ambiguities=[],
    )
    hypothesis = RootCauseHypothesis(
        incident_id="inc-1",
        suspected_root_cause_service="checkout-service",
        root_cause_support=0.88,
        contributing_signals=["latency_spike"],
        impacted_downstream_services=["api-service"],
        unresolved_ambiguities=[],
        rationale="checkout-service shows dominant evidence",
    )
    return bundle, hypothesis


def test_validate_report_grounding_marks_supported_claims() -> None:
    bundle, hypothesis = _context()
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="checkout-service latency increased from 120.0 to 1800.0.",
        root_cause_explanation="checkout-service likely caused the incident.",
        executive_summary="checkout-service latency increased during the incident window.",
        engineering_handoff="checkout-service shows dominant evidence.",
        remediation_suggestions=["Inspect recent deployments and configuration changes."],
        facts=["checkout-service latency_spike observed 1800.0 baseline 120.0"],
        inferences=["checkout-service shows dominant evidence"],
        uncertainties=[],
    )

    summary = validate_report_grounding(
        report=report,
        evidence_bundle=bundle,
        root_cause_hypothesis=hypothesis,
        retrieved_context=[],
        config=GroundingConfig(enabled=True, policy="fail", minimum_support_overlap=0.2),
    )

    assert summary.passed is True
    assert summary.unsupported_claims == 0
    assert summary.contradictory_claims == 0
    assert any(item.section == "incident_summary" for item in summary.claims)
    assert any(item.status is ClaimValidationStatus.NOT_APPLICABLE for item in summary.claims)
    claim_citations = build_claim_citations(
        report=report,
        evidence_bundle=bundle,
        root_cause_hypothesis=hypothesis,
        retrieved_context=[],
        minimum_support_overlap=0.2,
    )
    assert claim_citations
    assert all(item.support_ids for item in claim_citations)


def test_validate_report_grounding_detects_unsupported_generated_claims() -> None:
    bundle, hypothesis = _context()
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="A Kubernetes deployment at 11:03 caused the outage.",
        root_cause_explanation="A database failure caused checkout-service impact.",
        executive_summary="Packet loss affected checkout-service.",
        engineering_handoff="checkout-service latency increased from 120.0 to 1800.0.",
        remediation_suggestions=[],
        facts=[],
        inferences=[],
        uncertainties=[],
    )
    snippet = RetrievedSnippet(
        citation_id="data/knowledge/runbooks/checkout_latency.md#chunk-1",
        source_path="data/knowledge/runbooks/checkout_latency.md",
        score=2.0,
        content="checkout-service latency_spike mitigation guidance",
    )

    summary = validate_report_grounding(
        report=report,
        evidence_bundle=bundle,
        root_cause_hypothesis=hypothesis,
        retrieved_context=[snippet],
        config=GroundingConfig(enabled=True, policy="fail", minimum_support_overlap=0.34),
    )

    assert summary.passed is False
    assert summary.unsupported_claims >= 3
    assert any(
        "Kubernetes deployment" in item.text and item.status is ClaimValidationStatus.UNSUPPORTED
        for item in summary.claims
    )
    assert any(
        "database failure" in item.text and item.status is ClaimValidationStatus.UNSUPPORTED
        for item in summary.claims
    )
    assert any(
        "Packet loss" in item.text and item.status is ClaimValidationStatus.UNSUPPORTED
        for item in summary.claims
    )
    assert any(
        "latency increased" in item.text and item.status is ClaimValidationStatus.SUPPORTED
        for item in summary.claims
    )


def test_validate_report_grounding_detects_wrong_affected_service() -> None:
    bundle, hypothesis = _context()
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="worker-service latency increased from 120.0 to 1800.0.",
        root_cause_explanation="checkout-service likely caused the incident.",
        executive_summary="checkout-service latency increased.",
        engineering_handoff="checkout-service shows dominant evidence.",
        remediation_suggestions=[],
        facts=[],
        inferences=[],
        uncertainties=[],
    )

    summary = validate_report_grounding(
        report=report,
        evidence_bundle=bundle,
        root_cause_hypothesis=hypothesis,
        retrieved_context=[],
        config=GroundingConfig(enabled=True, policy="fail", minimum_support_overlap=0.2),
    )

    assert summary.passed is False
    assert any(
        item.status is ClaimValidationStatus.CONTRADICTORY and "worker-service latency" in item.text
        for item in summary.claims
    )


def test_validate_report_grounding_does_not_accept_service_only_support() -> None:
    bundle, hypothesis = _context()
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="checkout-service database failed during the incident.",
        root_cause_explanation="checkout-service likely caused the incident.",
        executive_summary="checkout-service latency increased.",
        engineering_handoff="checkout-service shows dominant evidence.",
        remediation_suggestions=[],
        facts=["checkout-service database failed"],
        inferences=[],
        uncertainties=[],
    )

    summary = validate_report_grounding(
        report=report,
        evidence_bundle=bundle,
        root_cause_hypothesis=hypothesis,
        retrieved_context=[],
        config=GroundingConfig(enabled=True, policy="fail", minimum_support_overlap=0.34),
    )

    assert summary.passed is False
    assert any(
        "database failed" in item.text and item.status is ClaimValidationStatus.UNSUPPORTED
        for item in summary.claims
    )


def test_validate_report_grounding_supports_error_rate_claim() -> None:
    bundle, hypothesis = _context(
        [
            _anomaly(
                anomaly_type="error_rate_spike",
                affected_service="api-service",
                evidence_summary="api-service error rate increased",
                observed_value=0.22,
                baseline_value=0.01,
            )
        ]
    )
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="api-service error rate increased from 0.01 to 0.22.",
        root_cause_explanation="checkout-service likely caused the incident.",
        executive_summary="api-service errors increased during the incident window.",
        engineering_handoff="api-service error_rate_spike observed 0.22 baseline 0.01.",
        remediation_suggestions=[],
        facts=[],
        inferences=[],
        uncertainties=[],
    )

    summary = validate_report_grounding(
        report=report,
        evidence_bundle=bundle,
        root_cause_hypothesis=hypothesis,
        retrieved_context=[],
        config=GroundingConfig(enabled=True, policy="fail", minimum_support_overlap=0.2),
    )

    assert summary.passed is True
    assert any(
        item.status is ClaimValidationStatus.SUPPORTED and "error rate increased" in item.text
        for item in summary.claims
    )


def test_validate_report_grounding_marks_non_factual_claims_not_applicable() -> None:
    bundle, hypothesis = _context()
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="checkout-service latency increased from 120.0 to 1800.0.",
        root_cause_explanation="checkout-service likely caused the incident.",
        executive_summary="checkout-service latency increased.",
        engineering_handoff="checkout-service shows dominant evidence.",
        remediation_suggestions=["Review recent changes."],
        facts=[],
        inferences=[],
        uncertainties=["The exact deployment status is unknown."],
    )

    summary = validate_report_grounding(
        report=report,
        evidence_bundle=bundle,
        root_cause_hypothesis=hypothesis,
        retrieved_context=[],
        config=GroundingConfig(enabled=True, policy="fail", minimum_support_overlap=0.2),
    )

    assert summary.passed is True
    assert any(
        item.claim_type is ClaimType.UNCERTAINTY
        and item.status is ClaimValidationStatus.NOT_APPLICABLE
        for item in summary.claims
    )
    assert any(
        item.claim_type is ClaimType.RECOMMENDATION
        and item.status is ClaimValidationStatus.NOT_APPLICABLE
        for item in summary.claims
    )
