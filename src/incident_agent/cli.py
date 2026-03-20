"""CLI entrypoints for the incident analysis agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from incident_agent.ingestion.logs import ingest_logs
from incident_agent.ingestion.metrics import ingest_metrics
from incident_agent.services.analyze import analyze_from_files
from incident_agent.services.detect import detect_anomalies_from_files
from incident_agent.services.normalize import normalize_from_files

app = typer.Typer(help="CLI for the AI incident analysis agent.")
console = Console()


@app.command()
def analyze(
    logs: Annotated[
        str, typer.Option(help="Path to logs file (.jsonl or .csv).")
    ],
    metrics: Annotated[
        str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")
    ],
) -> None:
    """Analyze logs and metrics and print structured reports."""

    reports = analyze_from_files(log_path=logs, metric_path=metrics)
    serialised = [report.model_dump(mode="json") for report in reports]
    console.print_json(json.dumps(serialised))


@app.command("validate-data")
def validate_data(
    logs: Annotated[
        str, typer.Option(help="Path to logs file (.jsonl or .csv).")
    ],
    metrics: Annotated[
        str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")
    ],
) -> None:
    """Validate datasets and print quality metrics."""

    logs_result = ingest_logs(logs)
    metrics_result = ingest_metrics(metrics)

    table = Table(title="Data Quality Report")
    table.add_column("Dataset")
    table.add_column("Total", justify="right")
    table.add_column("Valid", justify="right")
    table.add_column("Invalid", justify="right")
    table.add_column("Dropped Duplicates", justify="right")
    table.add_column("Parse Warnings", justify="right")

    for dataset_name, report in (
        ("logs", logs_result.report),
        ("metrics", metrics_result.report),
    ):
        table.add_row(
            dataset_name,
            str(report.total_rows),
            str(report.valid_rows),
            str(report.invalid_rows),
            str(report.dropped_duplicates),
            str(report.parse_warnings),
        )
    console.print(table)


@app.command("ingest-data")
def ingest_data(
    logs: Annotated[
        str, typer.Option(help="Path to logs file (.jsonl or .csv).")
    ],
    metrics: Annotated[
        str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")
    ],
    output_dir: Annotated[
        str, typer.Option(help="Directory to write normalized artifacts.")
    ] = "artifacts/ingestion",
) -> None:
    """Ingest datasets and persist normalized records plus quality reports."""

    logs_result = ingest_logs(logs)
    metrics_result = ingest_metrics(metrics)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    _write_jsonl(
        target / "normalized_logs.jsonl",
        [record.model_dump(mode="json") for record in logs_result.records],
    )
    _write_jsonl(
        target / "normalized_metrics.jsonl",
        [record.model_dump(mode="json") for record in metrics_result.records],
    )
    quality_payload = {
        "logs": logs_result.report.model_dump(mode="json"),
        "metrics": metrics_result.report.model_dump(mode="json"),
    }
    (target / "ingestion_report.json").write_text(
        json.dumps(quality_payload, indent=2),
        encoding="utf-8",
    )
    console.print(f"Wrote normalized ingestion artifacts to {target}")


@app.command("normalize-timeline")
def normalize_timeline(
    logs: Annotated[
        str, typer.Option(help="Path to logs file (.jsonl or .csv).")
    ],
    metrics: Annotated[
        str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")
    ],
    config: Annotated[
        str, typer.Option(help="Path to YAML config file.")
    ] = "configs/default.yaml",
    bucket_size_minutes: Annotated[
        int | None, typer.Option(help="Override bucket size (1, 5, 15).")
    ] = None,
) -> None:
    """Normalize and align events to timeline buckets."""

    alignment = normalize_from_files(
        log_path=logs,
        metric_path=metrics,
        config_path=config,
        bucket_size_minutes=bucket_size_minutes,
    )
    payload = {
        "events": [event.model_dump(mode="json") for event in alignment.events],
        "buckets": [bucket.model_dump(mode="json") for bucket in alignment.buckets],
    }
    console.print_json(json.dumps(payload))


@app.command("detect-anomalies")
def detect_anomalies_command(
    logs: Annotated[
        str, typer.Option(help="Path to logs file (.jsonl or .csv).")
    ],
    metrics: Annotated[
        str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")
    ],
    config: Annotated[
        str, typer.Option(help="Path to YAML config file.")
    ] = "configs/default.yaml",
    bucket_size_minutes: Annotated[
        int | None, typer.Option(help="Override bucket size (1, 5, 15).")
    ] = None,
) -> None:
    """Run deterministic anomaly detectors and print candidates."""

    result = detect_anomalies_from_files(
        log_path=logs,
        metric_path=metrics,
        config_path=config,
        bucket_size_minutes=bucket_size_minutes,
    )
    payload = [anomaly.model_dump(mode="json") for anomaly in result.anomalies]
    console.print_json(json.dumps(payload))


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


if __name__ == "__main__":
    app()
