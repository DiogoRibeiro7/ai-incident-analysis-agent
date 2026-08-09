from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from incident_agent.knowledge.retrieval import RetrievedSnippet
from incident_agent.prompts.renderer import PromptRenderContext, render_all_prompts, render_prompt
from incident_agent.schemas.anomaly import AnomalyCandidate
from incident_agent.schemas.rca import EvidenceBundle, IncidentSummaryFeatures, RootCauseHypothesis


def _context() -> PromptRenderContext:
    start = datetime(2026, 3, 20, 11, 15, tzinfo=UTC)
    evidence = AnomalyCandidate(
        timestamp_window_start=start,
        timestamp_window_end=start + timedelta(minutes=5),
        anomaly_type="latency_spike",
        affected_service="checkout-service",
        severity_score=9.5,
        observed_value=1900.0,
        baseline_value=120.0,
        evidence_summary="latency exceeded baseline",
        scope="service",
    )
    return PromptRenderContext(
        incident_id="inc-20260320T111500Z-001",
        evidence_bundle=EvidenceBundle(
            incident_id="inc-20260320T111500Z-001",
            ranked_evidence=[evidence],
            contributing_signals=["latency_spike"],
            impacted_downstream_services=["api-service"],
            unresolved_ambiguities=[],
        ),
        summary_features=IncidentSummaryFeatures(
            incident_id="inc-20260320T111500Z-001",
            total_evidence=1,
            impacted_services=["checkout-service", "api-service"],
            anomaly_type_counts={"latency_spike": 1},
            service_evidence_counts={"checkout-service": 1},
            average_severity=9.5,
            peak_severity=9.5,
        ),
        root_cause_hypothesis=RootCauseHypothesis(
            incident_id="inc-20260320T111500Z-001",
            suspected_root_cause_service="checkout-service",
            root_cause_support=0.88,
            contributing_signals=["latency_spike"],
            impacted_downstream_services=["api-service"],
            unresolved_ambiguities=[],
            rationale="Dominant service-level latency signal.",
        ),
        retrieved_context=[
            RetrievedSnippet(
                citation_id=f"{Path('data/knowledge/runbooks/checkout_latency.md').as_posix()}#chunk-1",
                source_path=Path("data/knowledge/runbooks/checkout_latency.md").as_posix(),
                score=3.0,
                content=(
                    "If checkout-service shows sustained latency_spike, verify upstream "
                    "database saturation."
                ),
            )
        ],
    )


def test_render_prompt_includes_guardrails_and_structured_payload() -> None:
    rendered = render_prompt("incident_summary", _context())

    assert "Use only the provided evidence" in rendered
    assert "Do not invent services, metrics, timestamps, or events." in rendered
    assert '"incident_id": "inc-20260320T111500Z-001"' in rendered
    assert '"suspected_root_cause_service": "checkout-service"' in rendered
    assert '"retrieved_context": [' in rendered


def test_render_all_prompts_returns_all_template_variants() -> None:
    rendered = render_all_prompts(_context())

    assert set(rendered.keys()) == {
        "incident_summary",
        "root_cause_explanation",
        "executive_summary",
        "engineering_handoff",
        "remediation_suggestions",
    }
