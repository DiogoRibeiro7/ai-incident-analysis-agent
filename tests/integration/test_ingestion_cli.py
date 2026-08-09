from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from incident_agent.cli import app


def test_validate_data_command(tmp_path: Path) -> None:
    logs_path = tmp_path / "logs.jsonl"
    logs_path.write_text(
        '{"timestamp":"2026-03-20T10:00:00Z","service":"api","severity":"ERROR","message":"boom"}\n',
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-03-20T10:00:00Z",
                    "service": "api",
                    "metric_name": "error_rate",
                    "value": 0.2,
                }
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "validate-data",
            "--logs",
            str(logs_path),
            "--metrics",
            str(metrics_path),
        ],
    )

    assert result.exit_code == 0
    assert "Data Quality Report" in result.stdout


def test_run_pipeline_command_rejects_disallowed_path(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-pipeline",
            "--logs",
            "../secrets/logs.csv",
            "--metrics",
            "data/sample/incident/anomaly_metrics.csv",
            "--artifact-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0


def test_ingest_data_command_writes_artifacts(tmp_path: Path) -> None:
    logs_path = tmp_path / "logs.csv"
    logs_path.write_text(
        "\n".join(
            [
                "timestamp,service,severity,message",
                "2026-03-20T10:00:00Z,api,ERROR,boom",
            ]
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.csv"
    metrics_path.write_text(
        "\n".join(
            [
                "timestamp,service,metric_name,value",
                "2026-03-20T10:00:00Z,api,error_rate,0.2",
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ingest-data",
            "--logs",
            str(logs_path),
            "--metrics",
            str(metrics_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "normalized_logs.jsonl").exists()
    assert (output_dir / "normalized_metrics.jsonl").exists()
    assert (output_dir / "ingestion_report.json").exists()


def test_normalize_timeline_command_outputs_buckets(tmp_path: Path) -> None:
    logs_path = tmp_path / "logs.csv"
    logs_path.write_text(
        "\n".join(
            [
                "timestamp,service,severity,message",
                "2026-03-20T10:00:00Z,api,ERROR,boom",
            ]
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.csv"
    metrics_path.write_text(
        "\n".join(
            [
                "timestamp,service,metric_name,value",
                "2026-03-20T10:00:30Z,api,request_latency_ms,1200",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "normalize-timeline",
            "--logs",
            str(logs_path),
            "--metrics",
            str(metrics_path),
            "--bucket-size-minutes",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert '"buckets"' in result.stdout


def test_detect_anomalies_command_outputs_candidates() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "detect-anomalies",
            "--logs",
            "data/sample/incident/anomaly_logs.csv",
            "--metrics",
            "data/sample/incident/anomaly_metrics.csv",
            "--bucket-size-minutes",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "latency_spike" in result.stdout


def test_correlate_incidents_command_outputs_incidents() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "correlate-incidents",
            "--logs",
            "data/sample/incident/anomaly_logs.csv",
            "--metrics",
            "data/sample/incident/anomaly_metrics.csv",
            "--bucket-size-minutes",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "incident_id" in result.stdout


def test_run_rca_command_outputs_hypotheses() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-rca",
            "--logs",
            "data/sample/incident/anomaly_logs.csv",
            "--metrics",
            "data/sample/incident/anomaly_metrics.csv",
            "--bucket-size-minutes",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "suspected_root_cause_service" in result.stdout


def test_run_pipeline_command_outputs_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-pipeline",
            "--logs",
            "data/sample/incident/anomaly_logs.csv",
            "--metrics",
            "data/sample/incident/anomaly_metrics.csv",
            "--artifact-root",
            str(tmp_path),
            "--bucket-size-minutes",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "final_report_count" in result.stdout


def test_print_config_command_outputs_yaml_as_json() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["print-config"])

    assert result.exit_code == 0
    assert '"llm"' in result.stdout


def test_list_incidents_and_show_report_commands(tmp_path: Path) -> None:
    run_dir = _prepare_pipeline_artifacts(tmp_path)
    runner = CliRunner()

    list_result = runner.invoke(
        app,
        [
            "list-incidents",
            "--artifact-dir",
            str(run_dir),
        ],
    )
    show_result = runner.invoke(
        app,
        [
            "show-report",
            "--artifact-dir",
            str(run_dir),
            "--index",
            "0",
        ],
    )

    assert list_result.exit_code == 0
    assert "Incident ID" in list_result.stdout
    assert show_result.exit_code == 0
    assert '"incident_id"' in show_result.stdout


def test_list_reports_command_with_review_status_filter(tmp_path: Path) -> None:
    run_dir = _prepare_pipeline_artifacts(tmp_path)
    reports_path = run_dir / "reports" / "final_reports.json"
    incident_id = json.loads(reports_path.read_text(encoding="utf-8"))[0]["incident_id"]
    runner = CliRunner()

    reviewed = runner.invoke(
        app,
        [
            "mark-reviewed",
            "--artifact-dir",
            str(run_dir),
            "--incident-id",
            incident_id,
            "--reviewer",
            "alice",
            "--note",
            "ready",
        ],
    )
    assert reviewed.exit_code == 0

    reviewed_only = runner.invoke(
        app,
        [
            "list-reports",
            "--artifact-dir",
            str(run_dir),
            "--review-status",
            "reviewed",
        ],
    )
    assert reviewed_only.exit_code == 0
    reviewed_payload = json.loads(reviewed_only.stdout)
    assert reviewed_payload
    assert all(item["review_status"] == "reviewed" for item in reviewed_payload)

    approved_only = runner.invoke(
        app,
        [
            "list-reports",
            "--artifact-dir",
            str(run_dir),
            "--review-status",
            "approved",
        ],
    )
    assert approved_only.exit_code == 0
    assert json.loads(approved_only.stdout) == []


def test_export_report_command_json_markdown_and_html(tmp_path: Path) -> None:
    run_dir = _prepare_pipeline_artifacts(tmp_path)
    runner = CliRunner()
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    output_html = tmp_path / "report.html"

    json_result = runner.invoke(
        app,
        [
            "export-report",
            "--artifact-dir",
            str(run_dir),
            "--output-path",
            str(output_json),
        ],
    )
    md_result = runner.invoke(
        app,
        [
            "export-report",
            "--artifact-dir",
            str(run_dir),
            "--output-path",
            str(output_md),
        ],
    )
    html_result = runner.invoke(
        app,
        [
            "export-report",
            "--artifact-dir",
            str(run_dir),
            "--output-path",
            str(output_html),
        ],
    )

    assert json_result.exit_code == 0
    assert md_result.exit_code == 0
    assert html_result.exit_code == 0
    assert output_json.exists()
    assert output_md.exists()
    assert output_html.exists()
    assert output_md.read_text(encoding="utf-8").startswith("# Incident Report")
    assert "<!DOCTYPE html>" in output_html.read_text(encoding="utf-8")


def test_show_report_fails_cleanly_when_report_file_is_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "missing-report-run"
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "show-report",
            "--artifact-dir",
            str(run_dir),
        ],
    )

    assert result.exit_code != 0


def test_review_commands_persist_status_and_history(tmp_path: Path) -> None:
    run_dir = _prepare_pipeline_artifacts(tmp_path)
    reports_path = run_dir / "reports" / "final_reports.json"
    reports = json.loads(reports_path.read_text(encoding="utf-8"))
    incident_id = reports[0]["incident_id"]
    runner = CliRunner()

    reviewed = runner.invoke(
        app,
        [
            "mark-reviewed",
            "--artifact-dir",
            str(run_dir),
            "--incident-id",
            incident_id,
            "--reviewer",
            "alice",
            "--note",
            "triage validated",
        ],
    )
    approved = runner.invoke(
        app,
        [
            "approve-report",
            "--artifact-dir",
            str(run_dir),
            "--incident-id",
            incident_id,
            "--reviewer",
            "alice",
            "--note",
            "approved",
        ],
    )

    assert reviewed.exit_code == 0
    assert approved.exit_code == 0
    updated = json.loads(reports_path.read_text(encoding="utf-8"))[0]
    assert updated["review_status"] == "approved"
    assert len(updated["review_history"]) == 2


def test_approve_report_fails_without_reviewed_status(tmp_path: Path) -> None:
    run_dir = _prepare_pipeline_artifacts(tmp_path)
    reports_path = run_dir / "reports" / "final_reports.json"
    reports = json.loads(reports_path.read_text(encoding="utf-8"))
    incident_id = reports[0]["incident_id"]
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "approve-report",
            "--artifact-dir",
            str(run_dir),
            "--incident-id",
            incident_id,
            "--reviewer",
            "alice",
            "--note",
            "skip review",
        ],
    )

    assert result.exit_code != 0


def test_export_approved_webhook_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(status_code=200, json={"payload_id": "hook-1"})

    monkeypatch.setattr("incident_agent.export.webhook.httpx.Client", _FakeClient)

    run_dir = _prepare_pipeline_artifacts(tmp_path)
    reports_path = run_dir / "reports" / "final_reports.json"
    incident_id = json.loads(reports_path.read_text(encoding="utf-8"))[0]["incident_id"]
    runner = CliRunner()
    runner.invoke(
        app,
        [
            "mark-reviewed",
            "--artifact-dir",
            str(run_dir),
            "--incident-id",
            incident_id,
            "--reviewer",
            "alice",
            "--note",
            "ok",
        ],
    )
    runner.invoke(
        app,
        [
            "approve-report",
            "--artifact-dir",
            str(run_dir),
            "--incident-id",
            incident_id,
            "--reviewer",
            "alice",
            "--note",
            "ok",
        ],
    )

    result = runner.invoke(
        app,
        [
            "export-approved-webhook",
            "--artifact-dir",
            str(run_dir),
            "--incident-id",
            incident_id,
            "--destination-url",
            "https://example.test/webhook",
        ],
    )
    assert result.exit_code == 0
    assert "delivered" in result.stdout
    audit_path = run_dir / "exports" / "webhook_deliveries.jsonl"
    assert audit_path.exists()


def _prepare_pipeline_artifacts(tmp_path: Path) -> Path:
    runner = CliRunner()
    artifact_root = tmp_path / "pipeline-artifacts"
    result = runner.invoke(
        app,
        [
            "run-pipeline",
            "--logs",
            "data/sample/incident/anomaly_logs.csv",
            "--metrics",
            "data/sample/incident/anomaly_metrics.csv",
            "--artifact-root",
            str(artifact_root),
            "--bucket-size-minutes",
            "5",
        ],
    )
    assert result.exit_code == 0
    runs = sorted([item for item in artifact_root.iterdir() if item.is_dir()])
    assert runs
    return runs[-1]


def test_run_eval_command_outputs_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-eval",
            "--benchmark-path",
            "eval/benchmarks/scenarios.json",
            "--artifact-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "records" in result.stdout
    assert "summaries" in result.stdout


def test_compare_eval_command_fails_on_regression(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline_summary.json"
    candidate_path = tmp_path / "candidate_summary.json"
    output_dir = tmp_path / "eval-compare"
    baseline_path.write_text(
        json.dumps(
            [
                {
                    "mode": "mock-llm-no-retrieval",
                    "runs": 1,
                    "success_rate": 1.0,
                    "root_cause_correctness": 0.6,
                    "impacted_service_correctness": 0.5,
                    "service_entity_precision": 1.0,
                    "unexpected_service_mention_rate": 0.0,
                    "citation_coverage": 1.0,
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
            ]
        ),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(
            [
                {
                    "mode": "mock-llm-no-retrieval",
                    "runs": 1,
                    "success_rate": 1.0,
                    "root_cause_correctness": 0.5,
                    "impacted_service_correctness": 0.5,
                    "service_entity_precision": 1.0,
                    "unexpected_service_mention_rate": 0.0,
                    "citation_coverage": 1.0,
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
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "compare-eval",
            "--baseline-summary-path",
            str(baseline_path),
            "--candidate-summary-path",
            str(candidate_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 1
    assert (output_dir / "eval_comparison.json").exists()
    assert (output_dir / "eval_comparison.md").exists()
