from __future__ import annotations

import json
from pathlib import Path

from incident_agent.eval.runner import _score_report, compare_evaluation_summaries, run_evaluation
from incident_agent.schemas.eval import BenchmarkScenario, EvaluationMode
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.schemas.grounding import (
    ClaimType,
    ClaimValidationStatus,
    GroundingClaimAssessment,
    GroundingSummary,
)


def _summary_row(mode: str, *, root_cause_correctness: float = 0.6) -> dict[str, object]:
    return {
        "mode": mode,
        "runs": 2,
        "success_rate": 1.0,
        "root_cause_correctness": root_cause_correctness,
        "impacted_service_correctness": 0.5,
        "service_entity_precision": 1.0,
        "unexpected_service_mention_rate": 0.0,
        "citation_coverage": 1.0,
        "retrieval_relevance": 0.0,
        "factual_claim_count": 2,
        "supported_factual_claim_count": 2,
        "unsupported_factual_claim_count": 0,
        "contradictory_factual_claim_count": 0,
        "factual_claim_support_rate": 1.0,
        "unsupported_factual_claim_rate": 0.0,
        "contradictory_factual_claim_rate": 0.0,
        "report_completeness": 1.0,
        "latency_seconds": 0.1,
        "average_token_usage": 0.0,
        "total_estimated_cost_usd": 0.0,
    }


def _write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_default_benchmark_corpus_is_labeled_and_has_detector_history() -> None:
    scenarios = json.loads(Path("eval/benchmarks/scenarios.json").read_text(encoding="utf-8"))

    assert 20 <= len(scenarios) <= 30
    scenario_types = {item["generator"]["scenario_type"] for item in scenarios}
    assert {
        "healthy_stable",
        "healthy_noisy",
        "normal_traffic_variability",
        "transient_latency_spike",
        "latency_degradation",
        "gradual_latency_drift",
        "error_burst",
        "persistent_error_rate",
        "error_logs_only",
        "metrics_only_degradation",
        "cpu_saturation",
        "memory_saturation",
        "resource_anomaly_no_impact",
        "traffic_drop",
        "traffic_disappearance",
        "isolated_low_volume_bucket",
        "heartbeat_loss",
        "temporary_unavailability",
        "missing_observability",
        "dependency_cascade",
        "upstream_root_cause",
        "downstream_symptoms",
        "unrelated_simultaneous",
        "ambiguous_root_causes",
        "contradictory_telemetry",
        "insufficient_evidence",
        "missing_logs",
        "missing_metrics",
        "sparse_observations",
    }.issubset(scenario_types)

    for scenario in scenarios:
        assert "incident_expected" in scenario
        assert "expected_impacted_services" in scenario
        assert "expected_anomaly_types" in scenario
        assert "expected_min_incidents" in scenario
        generator = scenario["generator"]
        assert generator["duration_minutes"] >= 60
        assert generator.get("interval_minutes", 5) <= 5


def test_run_evaluation_generates_summary_artifacts(tmp_path: Path) -> None:
    result = run_evaluation(
        benchmark_path="eval/benchmarks/scenarios.json",
        artifact_root=str(tmp_path),
        include_real_llm=False,
    )

    artifact_dir = Path(result.artifact_dir)
    assert artifact_dir.exists()
    assert (artifact_dir / "records.json").exists()
    assert (artifact_dir / "summary.json").exists()
    assert (artifact_dir / "summary.md").exists()
    assert result.records
    assert result.summaries
    modes = {item.mode for item in result.summaries}
    assert EvaluationMode.MOCK_LLM_NO_RETRIEVAL in modes
    assert EvaluationMode.MOCK_LLM_RETRIEVAL in modes
    retrieval_summary = next(
        item for item in result.summaries if item.mode is EvaluationMode.MOCK_LLM_RETRIEVAL
    )
    assert retrieval_summary.retrieval_relevance >= 0.0


def test_score_report_uses_claim_grounding_for_invented_fact() -> None:
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="Database connections exhausted after a failed deployment.",
        root_cause_explanation="checkout-service likely caused the incident.",
        executive_summary="checkout-service was degraded.",
        engineering_handoff="Review checkout-service evidence.",
        remediation_suggestions=["Review recent changes."],
    )
    grounding_summary = GroundingSummary(
        incident_id="inc-1",
        policy="fail",
        passed=False,
        total_claims=1,
        supported_claims=0,
        unsupported_claims=1,
        claims=[
            GroundingClaimAssessment(
                claim_id="incident_summary-1",
                text="Database connections exhausted after a failed deployment.",
                section="incident_summary",
                claim_type=ClaimType.FACT,
                status=ClaimValidationStatus.UNSUPPORTED,
                supporting_evidence_ids=[],
                reason="insufficient_evidence_overlap",
            )
        ],
    )
    metrics = _score_report(
        scenario=BenchmarkScenario(
            scenario_id="scenario-1",
            description="scenario",
            logs_path="logs.csv",
            metrics_path="metrics.csv",
            expected_root_cause="checkout-service",
            expected_impacted_services=["checkout-service"],
        ),
        report=report,
        predicted_root="checkout-service",
        impacted_services=["checkout-service"],
        anomaly_types=["error_rate_spike"],
        incident_count=1,
        mode=EvaluationMode.MOCK_LLM_NO_RETRIEVAL,
        grounding_summary=grounding_summary,
        latency_seconds=0.1,
        token_usage=0,
        estimated_cost_usd=0.0,
    )

    assert metrics.service_entity_precision == 1.0
    assert metrics.factual_claim_support_rate == 0.0
    assert metrics.unsupported_factual_claim_rate == 1.0


def test_score_report_uses_labeled_detection_metrics() -> None:
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="api-service latency increased and errors rose.",
        root_cause_explanation="api-service is a plausible root cause.",
        executive_summary="api-service and checkout-service were degraded.",
        engineering_handoff="Review api-service and checkout-service.",
        remediation_suggestions=["Review recent changes."],
    )

    metrics = _score_report(
        scenario=BenchmarkScenario(
            scenario_id="ambiguous",
            description="ambiguous",
            logs_path="logs.csv",
            metrics_path="metrics.csv",
            incident_expected=True,
            expected_root_cause="checkout-service",
            allowed_root_causes=["api-service"],
            expected_impacted_services=["checkout-service", "api-service"],
            expected_anomaly_types=["latency_spike", "error_rate_spike"],
            expected_min_incidents=2,
            expected_max_incidents=2,
        ),
        report=report,
        predicted_root="api-service",
        impacted_services=["api-service", "checkout-service"],
        anomaly_types=["latency_spike"],
        incident_count=2,
        mode=EvaluationMode.MOCK_LLM_NO_RETRIEVAL,
        grounding_summary=None,
        latency_seconds=0.1,
        token_usage=0,
        estimated_cost_usd=0.0,
    )

    assert metrics.incident_expectation_correctness == 1.0
    assert metrics.incident_count_correctness == 1.0
    assert metrics.root_cause_correctness == 1.0
    assert metrics.impacted_service_f1 == 1.0
    assert metrics.anomaly_type_recall == 0.5


def test_compare_evaluation_summaries_passes_for_matching_modes(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    rows = [
        _summary_row(EvaluationMode.HEURISTIC_ONLY.value),
        _summary_row(EvaluationMode.MOCK_LLM_NO_RETRIEVAL.value),
        _summary_row(EvaluationMode.MOCK_LLM_RETRIEVAL.value),
    ]
    _write_summary(baseline_path, rows)
    _write_summary(candidate_path, rows)

    comparison = compare_evaluation_summaries(
        baseline_summary_path=str(baseline_path),
        candidate_summary_path=str(candidate_path),
    )

    assert comparison.passed is True
    assert comparison.findings == []


def test_compare_evaluation_summaries_detects_missing_mode(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    _write_summary(
        baseline_path,
        [
            _summary_row(EvaluationMode.HEURISTIC_ONLY.value),
            _summary_row(EvaluationMode.MOCK_LLM_RETRIEVAL.value),
        ],
    )
    _write_summary(candidate_path, [_summary_row(EvaluationMode.HEURISTIC_ONLY.value)])

    comparison = compare_evaluation_summaries(
        baseline_summary_path=str(baseline_path),
        candidate_summary_path=str(candidate_path),
    )

    assert comparison.passed is False
    assert any(
        item.mode is EvaluationMode.MOCK_LLM_RETRIEVAL and item.metric == "mode_missing"
        for item in comparison.findings
    )


def test_compare_evaluation_summaries_detects_unexpected_mode(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    _write_summary(baseline_path, [_summary_row(EvaluationMode.HEURISTIC_ONLY.value)])
    _write_summary(
        candidate_path,
        [
            _summary_row(EvaluationMode.HEURISTIC_ONLY.value),
            _summary_row(EvaluationMode.REAL_LLM_RETRIEVAL.value),
        ],
    )

    comparison = compare_evaluation_summaries(
        baseline_summary_path=str(baseline_path),
        candidate_summary_path=str(candidate_path),
    )

    assert comparison.passed is False
    assert any(
        item.mode is EvaluationMode.REAL_LLM_RETRIEVAL and item.metric == "mode_unexpected"
        for item in comparison.findings
    )


def test_compare_evaluation_summaries_detects_regression(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    _write_summary(
        baseline_path,
        [_summary_row(EvaluationMode.MOCK_LLM_NO_RETRIEVAL.value, root_cause_correctness=0.5)],
    )
    _write_summary(
        candidate_path,
        [_summary_row(EvaluationMode.MOCK_LLM_NO_RETRIEVAL.value, root_cause_correctness=0.4)],
    )

    comparison = compare_evaluation_summaries(
        baseline_summary_path=str(baseline_path),
        candidate_summary_path=str(candidate_path),
    )

    assert comparison.passed is False
    assert any(item.metric == "root_cause_correctness" for item in comparison.findings)
