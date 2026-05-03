from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

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


def test_retrieve_context_loads_historical_incident_corpus_json(tmp_path: Path) -> None:
    bundle, summary, hypothesis = _build_rca_context()
    corpus_path = tmp_path / "historical_incidents.json"
    corpus_path.write_text(
        json.dumps(
            {
                "historical_incidents": [
                    {
                        "incident_id": "hist-1",
                        "primary_service": "checkout-service",
                        "impacted_services": ["api-service"],
                        "anomaly_types": ["latency_spike"],
                        "incident_summary": "Checkout latency spike during deploy.",
                        "root_cause": "checkout-service connection pool saturation",
                        "resolution": "Rollback and scale pool",
                        "tags": ["payments", "latency"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    config = KnowledgeConfig(
        enabled=True,
        source_paths=[str(corpus_path)],
        top_k=3,
        max_snippet_chars=500,
    )
    retrieved = retrieve_context(
        config=config,
        evidence_bundle=bundle,
        summary_features=summary,
        root_cause_hypothesis=hypothesis,
    )

    assert retrieved
    content = retrieved[0].content
    assert "incident_id=hist-1" in content
    assert "primary_service=checkout-service" in content
    assert "root_cause=checkout-service connection pool saturation" in content


def test_retrieve_context_loads_historical_incident_corpus_jsonl(tmp_path: Path) -> None:
    bundle, summary, hypothesis = _build_rca_context()
    corpus_path = tmp_path / "historical_incidents.jsonl"
    corpus_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "incident_id": "hist-jsonl-1",
                        "service": "checkout-service",
                        "summary": "Latency and error burst in checkout-service.",
                        "root_cause_service": "checkout-service",
                        "impacted_services": ["api-service"],
                    }
                ),
                '{"raw":"line"}',
            ]
        ),
        encoding="utf-8",
    )

    config = KnowledgeConfig(
        enabled=True,
        source_paths=[str(corpus_path)],
        top_k=2,
        max_snippet_chars=400,
    )
    retrieved = retrieve_context(
        config=config,
        evidence_bundle=bundle,
        summary_features=summary,
        root_cause_hypothesis=hypothesis,
    )

    assert retrieved
    assert any("incident_id=hist-jsonl-1" in item.content for item in retrieved)


def test_retrieve_context_chunks_markdown_runbook_by_section(tmp_path: Path) -> None:
    bundle, summary, hypothesis = _build_rca_context()
    runbook_path = tmp_path / "checkout_runbook.md"
    runbook_path.write_text(
        "\n".join(
            [
                "# Triage",
                "Check checkout-service latency and error rate dashboards.",
                "",
                "## Mitigation",
                "Roll back recent checkout-service deployment if p95 keeps rising.",
            ]
        ),
        encoding="utf-8",
    )
    config = KnowledgeConfig(
        enabled=True,
        source_paths=[str(runbook_path)],
        top_k=5,
        max_snippet_chars=500,
    )

    retrieved = retrieve_context(
        config=config,
        evidence_bundle=bundle,
        summary_features=summary,
        root_cause_hypothesis=hypothesis,
    )

    assert retrieved
    content = " ".join(item.content for item in retrieved).lower()
    assert "section=triage" in content
    assert "section=mitigation" in content


def test_retrieve_context_skips_malformed_json_file(tmp_path: Path) -> None:
    bundle, summary, hypothesis = _build_rca_context()
    bad_path = tmp_path / "broken.json"
    bad_path.write_text("{not-valid-json", encoding="utf-8")
    config = KnowledgeConfig(
        enabled=True,
        source_paths=[str(bad_path)],
        top_k=3,
        max_snippet_chars=400,
    )

    retrieved = retrieve_context(
        config=config,
        evidence_bundle=bundle,
        summary_features=summary,
        root_cause_hypothesis=hypothesis,
    )

    assert retrieved == []
