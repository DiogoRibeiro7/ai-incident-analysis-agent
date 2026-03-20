from __future__ import annotations

from pathlib import Path

from incident_agent.services.pipeline import run_pipeline_from_files


def test_run_pipeline_from_files_persists_artifacts(tmp_path: Path) -> None:
    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        artifact_root=str(tmp_path),
        bucket_size_minutes=5,
    )

    run_dir = Path(result.artifact_dir)
    assert run_dir.exists()
    assert (run_dir / "normalized" / "timeline.json").exists()
    assert (run_dir / "anomalies" / "anomalies.json").exists()
    assert (run_dir / "incidents" / "incidents.json").exists()
    assert (run_dir / "rca" / "rca_hypotheses.json").exists()
    assert (run_dir / "reports" / "final_reports.json").exists()
    assert result.final_report_count >= 1
