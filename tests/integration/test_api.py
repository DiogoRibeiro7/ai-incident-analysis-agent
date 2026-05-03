from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from incident_agent.api.main import app
from incident_agent.api.store import AnalysisJobStore


def _client() -> TestClient:
    app.state.job_store = AnalysisJobStore()
    return TestClient(app)


def test_health_endpoint() -> None:
    client = _client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_inspection_success() -> None:
    client = _client()
    response = client.get("/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_path"] == "configs/default.yaml"
    assert "llm" in payload["config"]


def test_config_inspection_failure_for_missing_file() -> None:
    client = _client()
    response = client.get("/config", params={"config_path": "configs/missing.yaml"})

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_analyze_pipeline_endpoint(tmp_path: Path) -> None:
    client = _client()
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


def test_submit_job_and_retrieve_outputs(tmp_path: Path) -> None:
    client = _client()
    submit = client.post(
        "/analysis-jobs",
        json={
            "logs_path": "data/sample/incident/anomaly_logs.csv",
            "metrics_path": "data/sample/incident/anomaly_metrics.csv",
            "artifact_root": str(tmp_path),
            "bucket_size_minutes": 5,
        },
    )
    assert submit.status_code == 200
    submitted = submit.json()
    assert submitted["status"] == "completed"
    job_id = submitted["job_id"]

    report_response = client.get(f"/analysis-jobs/{job_id}/reports")
    assert report_response.status_code == 200
    assert report_response.json()["reports"]

    incidents_response = client.get("/incidents", params={"job_id": job_id})
    assert incidents_response.status_code == 200
    assert incidents_response.json()["incidents"]

    anomalies_response = client.get("/anomalies", params={"job_id": job_id})
    assert anomalies_response.status_code == 200
    assert anomalies_response.json()["anomalies"]


def test_report_review_transitions_for_job(tmp_path: Path) -> None:
    client = _client()
    submit = client.post(
        "/analysis-jobs",
        json={
            "logs_path": "data/sample/incident/anomaly_logs.csv",
            "metrics_path": "data/sample/incident/anomaly_metrics.csv",
            "artifact_root": str(tmp_path),
            "bucket_size_minutes": 5,
        },
    )
    assert submit.status_code == 200
    job_id = submit.json()["job_id"]

    reports_response = client.get(f"/analysis-jobs/{job_id}/reports")
    incident_id = reports_response.json()["reports"][0]["incident_id"]

    reviewed = client.post(
        f"/analysis-jobs/{job_id}/reports/{incident_id}/review",
        json={"to_status": "reviewed", "reviewer": "alice", "note": "looks consistent"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["report"]["review_status"] == "reviewed"
    assert len(reviewed.json()["report"]["review_history"]) == 1

    approved = client.post(
        f"/analysis-jobs/{job_id}/reports/{incident_id}/review",
        json={"to_status": "approved", "reviewer": "alice", "note": "approved for share"},
    )
    assert approved.status_code == 200
    assert approved.json()["report"]["review_status"] == "approved"
    assert len(approved.json()["report"]["review_history"]) == 2


def test_report_review_invalid_transition_returns_400(tmp_path: Path) -> None:
    client = _client()
    submit = client.post(
        "/analysis-jobs",
        json={
            "logs_path": "data/sample/incident/anomaly_logs.csv",
            "metrics_path": "data/sample/incident/anomaly_metrics.csv",
            "artifact_root": str(tmp_path),
            "bucket_size_minutes": 5,
        },
    )
    assert submit.status_code == 200
    job_id = submit.json()["job_id"]

    reports_response = client.get(f"/analysis-jobs/{job_id}/reports")
    incident_id = reports_response.json()["reports"][0]["incident_id"]
    invalid = client.post(
        f"/analysis-jobs/{job_id}/reports/{incident_id}/review",
        json={"to_status": "approved", "reviewer": "alice", "note": "skip step"},
    )
    assert invalid.status_code == 400
    assert "Invalid review transition" in invalid.json()["detail"]


def test_job_related_endpoints_return_404_for_unknown_job() -> None:
    client = _client()

    reports = client.get("/analysis-jobs/job-missing/reports")
    incidents = client.get("/incidents", params={"job_id": "job-missing"})
    anomalies = client.get("/anomalies", params={"job_id": "job-missing"})

    assert reports.status_code == 404
    assert incidents.status_code == 404
    assert anomalies.status_code == 404


def test_submit_job_failure_for_missing_input_files(tmp_path: Path) -> None:
    client = _client()
    response = client.post(
        "/analysis-jobs",
        json={
            "logs_path": "data/sample/missing-logs.csv",
            "metrics_path": "data/sample/missing-metrics.csv",
            "artifact_root": str(tmp_path),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
