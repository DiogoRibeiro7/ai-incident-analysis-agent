from __future__ import annotations

from incident_agent.services.rca import run_rca_from_files


def test_run_rca_from_files_generates_hypothesis() -> None:
    result = run_rca_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        bucket_size_minutes=5,
    )

    assert result.hypotheses
    assert result.bundles
    assert result.summaries
    assert result.hypotheses[0].suspected_root_cause_service == "checkout-service"
