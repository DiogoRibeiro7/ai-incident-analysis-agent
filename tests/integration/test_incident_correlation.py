from __future__ import annotations

from incident_agent.services.correlate import correlate_incidents_from_files


def test_correlate_incidents_from_files_returns_candidates() -> None:
    result = correlate_incidents_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        bucket_size_minutes=5,
    )

    assert result.incidents
    first = result.incidents[0]
    assert first.correlation_score > 0
    assert first.suspected_primary_service == "checkout-service"
