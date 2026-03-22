from __future__ import annotations

import json
from pathlib import Path

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


def test_export_report_command_json_and_markdown(tmp_path: Path) -> None:
    run_dir = _prepare_pipeline_artifacts(tmp_path)
    runner = CliRunner()
    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"

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

    assert json_result.exit_code == 0
    assert md_result.exit_code == 0
    assert output_json.exists()
    assert output_md.exists()
    assert output_md.read_text(encoding="utf-8").startswith("# Incident Report")


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
