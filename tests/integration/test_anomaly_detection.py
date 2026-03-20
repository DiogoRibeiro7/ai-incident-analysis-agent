from __future__ import annotations

from incident_agent.services.detect import detect_anomalies_from_files


def test_detect_anomalies_from_sample_scenario_covers_all_types() -> None:
    result = detect_anomalies_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        bucket_size_minutes=5,
    )
    detected_types = {anomaly.anomaly_type for anomaly in result.anomalies}

    assert "error_rate_spike" in detected_types
    assert "latency_spike" in detected_types
    assert "cpu_anomaly" in detected_types
    assert "memory_anomaly" in detected_types
    assert "traffic_drop" in detected_types
    assert "service_unavailability" in detected_types
