from __future__ import annotations

from datetime import UTC, datetime, timedelta

from incident_agent.core.settings import KnowledgeConfig
from incident_agent.knowledge.retrieval import retrieve_context
from incident_agent.schemas.anomaly import AnomalyCandidate
from incident_agent.schemas.rca import EvidenceBundle, IncidentSummaryFeatures, RootCauseHypothesis


def _build_rca_context() -> tuple[EvidenceBundle, IncidentSummaryFeatures, RootCauseHypothesis]:
    start = datetime(2026, 3, 20, 11, 15, tzinfo=UTC)
    evidence = AnomalyCandidate(
        timestamp_window_start=start,
        timestamp_window_end=start + timedelta(minutes=5),
        anomaly_type="latency_spike",
        affected_service="checkout-service",
        severity_score=9.2,
        observed_value=1880.0,
        baseline_value=115.0,
        evidence_summary="latency exceeded baseline",
        scope="service",
    )
    bundle = EvidenceBundle(
        incident_id="inc-1",
        ranked_evidence=[evidence],
        contributing_signals=["latency_spike"],
        impacted_downstream_services=["api-service"],
        unresolved_ambiguities=[],
    )
    summary = IncidentSummaryFeatures(
        incident_id="inc-1",
        total_evidence=1,
        impacted_services=["checkout-service", "api-service"],
        anomaly_type_counts={"latency_spike": 1},
        service_evidence_counts={"checkout-service": 1},
        average_severity=9.2,
        peak_severity=9.2,
    )
    hypothesis = RootCauseHypothesis(
        incident_id="inc-1",
        suspected_root_cause_service="checkout-service",
        confidence_score=0.87,
        contributing_signals=["latency_spike"],
        impacted_downstream_services=["api-service"],
        unresolved_ambiguities=[],
        rationale="checkout-service has dominant severity",
    )
    return bundle, summary, hypothesis


def test_retrieve_context_returns_deterministic_top_k() -> None:
    bundle, summary, hypothesis = _build_rca_context()
    config = KnowledgeConfig(
        enabled=True,
        source_paths=["data/knowledge/runbooks", "data/knowledge/incidents"],
        top_k=2,
        max_snippet_chars=280,
    )

    first = retrieve_context(
        config=config,
        evidence_bundle=bundle,
        summary_features=summary,
        root_cause_hypothesis=hypothesis,
    )
    second = retrieve_context(
        config=config,
        evidence_bundle=bundle,
        summary_features=summary,
        root_cause_hypothesis=hypothesis,
    )

    assert len(first) == 2
    assert [item.citation_id for item in first] == [item.citation_id for item in second]
    assert first[0].score >= first[1].score
    assert any("checkout" in item.content.lower() for item in first)


def test_retrieve_context_returns_empty_when_disabled() -> None:
    bundle, summary, hypothesis = _build_rca_context()
    config = KnowledgeConfig(enabled=False, source_paths=["data/knowledge/runbooks"])

    retrieved = retrieve_context(
        config=config,
        evidence_bundle=bundle,
        summary_features=summary,
        root_cause_hypothesis=hypothesis,
    )

    assert retrieved == []
