from __future__ import annotations

import json
from pathlib import Path

from incident_agent.eval.runner import compare_evaluation_summaries, run_evaluation


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


def test_compare_evaluation_summaries_detects_regression(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(
        json.dumps(
            [
                {
                    "mode": "mock-llm",
                    "runs": 2,
                    "success_rate": 1.0,
                    "root_cause_correctness": 0.5,
                    "impacted_service_correctness": 0.5,
                    "factual_grounding": 1.0,
                    "hallucination_rate": 0.0,
                    "report_completeness": 1.0,
                    "latency_seconds": 0.1,
                    "average_token_usage": 0.0,
                    "total_estimated_cost_usd": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(
            [
                {
                    "mode": "mock-llm",
                    "runs": 2,
                    "success_rate": 1.0,
                    "root_cause_correctness": 0.4,
                    "impacted_service_correctness": 0.5,
                    "factual_grounding": 1.0,
                    "hallucination_rate": 0.0,
                    "report_completeness": 1.0,
                    "latency_seconds": 0.2,
                    "average_token_usage": 0.0,
                    "total_estimated_cost_usd": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )

    comparison = compare_evaluation_summaries(
        baseline_summary_path=str(baseline_path),
        candidate_summary_path=str(candidate_path),
    )
    assert comparison.passed is False
    assert any(item.metric == "root_cause_correctness" for item in comparison.findings)
