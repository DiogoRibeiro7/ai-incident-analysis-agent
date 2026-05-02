from __future__ import annotations

from datetime import UTC, datetime, timedelta

from incident_agent.core.settings import GroundingConfig
from incident_agent.grounding.validate import validate_report_grounding
from incident_agent.knowledge.retrieval import RetrievedSnippet
from incident_agent.schemas.anomaly import AnomalyCandidate
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.schemas.rca import EvidenceBundle, RootCauseHypothesis


def _context() -> tuple[EvidenceBundle, RootCauseHypothesis]:
    start = datetime(2026, 3, 20, 11, 15, tzinfo=UTC)
    evidence = AnomalyCandidate(
        timestamp_window_start=start,
        timestamp_window_end=start + timedelta(minutes=5),
        anomaly_type="latency_spike",
        affected_service="checkout-service",
        severity_score=9.4,
        observed_value=1800.0,
        baseline_value=120.0,
        evidence_summary="checkout-service latency increased",
        scope="service",
    )
    bundle = EvidenceBundle(
        incident_id="inc-1",
        ranked_evidence=[evidence],
        contributing_signals=["latency_spike"],
        impacted_downstream_services=["api-service"],
        unresolved_ambiguities=[],
    )
    hypothesis = RootCauseHypothesis(
        incident_id="inc-1",
        suspected_root_cause_service="checkout-service",
        confidence_score=0.88,
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
        incident_summary="summary",
        root_cause_explanation="root",
        executive_summary="exec",
        engineering_handoff="handoff",
        remediation_suggestions=[],
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


def test_validate_report_grounding_detects_unsupported_claims() -> None:
    bundle, hypothesis = _context()
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="summary",
        root_cause_explanation="root",
        executive_summary="exec",
        engineering_handoff="handoff",
        remediation_suggestions=[],
        facts=["worker-service memory_anomaly observed 900 baseline 100"],
        inferences=["unseen-service caused cascade"],
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
    assert summary.unsupported_claims >= 1
    assert any(item.reason == "insufficient_evidence_overlap" for item in summary.claims)
