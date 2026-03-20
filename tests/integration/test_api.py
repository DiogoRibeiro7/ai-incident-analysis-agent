from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from incident_agent.api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_pipeline_endpoint(tmp_path: Path) -> None:
    client = TestClient(app)
    response = client.post(
        "/analyze-pipeline",
        json={
            "logs_path": "data/sample/incident/anomaly_logs.csv",
            "metrics_path": "data/sample/incident/anomaly_metrics.csv",
            "artifact_root": str(tmp_path),
            "bucket_size_minutes": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_report_count"] >= 1
    assert (Path(payload["artifact_dir"]) / "reports" / "final_reports.json").exists()
