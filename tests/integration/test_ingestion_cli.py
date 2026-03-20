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
