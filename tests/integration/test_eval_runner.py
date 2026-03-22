from __future__ import annotations

from pathlib import Path

from incident_agent.eval.runner import run_evaluation


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
