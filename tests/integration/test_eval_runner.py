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
        mode=EvaluationMode.MOCK_LLM_NO_RETRIEVAL,
        grounding_summary=grounding_summary,
        latency_seconds=0.1,
        token_usage=0,
        estimated_cost_usd=0.0,
    )

    assert metrics.service_entity_precision == 1.0
    assert metrics.factual_claim_support_rate == 0.0
    assert metrics.unsupported_factual_claim_rate == 1.0


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
