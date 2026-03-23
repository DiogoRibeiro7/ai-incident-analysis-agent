"""CLI entrypoints for the incident analysis agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import click
import typer
from rich.console import Console
from rich.table import Table

from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.eval.runner import run_evaluation
from incident_agent.export.serializers import ExportFormat, serialize_report
from incident_agent.ingestion.logs import ingest_logs
from incident_agent.ingestion.metrics import ingest_metrics
from incident_agent.schemas.eval import (
    SyntheticScenarioGeneratorConfig,
    SyntheticScenarioType,
)
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.services.analyze import analyze_from_files
from incident_agent.services.correlate import correlate_incidents_from_files
from incident_agent.services.demo import run_demo
from incident_agent.services.detect import detect_anomalies_from_files
from incident_agent.services.normalize import normalize_from_files
from incident_agent.services.pipeline import run_pipeline_from_files
from incident_agent.services.rca import run_rca_from_files
from incident_agent.synthetic.generator import generate_benchmark_scenario
from incident_agent.utils.observability import configure_logging

app = typer.Typer(help="CLI for the AI incident analysis agent.")
console = Console()
configure_logging()


@app.command()
def analyze(
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
) -> None:
    """Analyze logs and metrics and print structured reports."""

    reports = analyze_from_files(log_path=logs, metric_path=metrics, config_path=config)
    serialised = [report.model_dump(mode="json") for report in reports]
    console.print_json(json.dumps(serialised))


@app.command("validate-data")
def validate_data(
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
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
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
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
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
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
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
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


@app.command("correlate-incidents")
def correlate_incidents_command(
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
    bucket_size_minutes: Annotated[
        int | None, typer.Option(help="Override bucket size (1, 5, 15).")
    ] = None,
) -> None:
    """Correlate anomaly candidates into incident candidates."""

    result = correlate_incidents_from_files(
        log_path=logs,
        metric_path=metrics,
        config_path=config,
        bucket_size_minutes=bucket_size_minutes,
    )
    payload = [incident.model_dump(mode="json") for incident in result.incidents]
    console.print_json(json.dumps(payload))


@app.command("run-rca")
def run_rca_command(
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
    bucket_size_minutes: Annotated[
        int | None, typer.Option(help="Override bucket size (1, 5, 15).")
    ] = None,
) -> None:
    """Run RCA on correlated incidents and print intermediate artifacts."""

    result = run_rca_from_files(
        log_path=logs,
        metric_path=metrics,
        config_path=config,
        bucket_size_minutes=bucket_size_minutes,
    )
    payload = {
        "bundles": [bundle.model_dump(mode="json") for bundle in result.bundles],
        "summaries": [summary.model_dump(mode="json") for summary in result.summaries],
        "hypotheses": [hypothesis.model_dump(mode="json") for hypothesis in result.hypotheses],
    }
    console.print_json(json.dumps(payload))


@app.command("run-pipeline")
def run_pipeline_command(
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
    artifact_root: Annotated[
        str, typer.Option(help="Root directory for pipeline artifacts.")
    ] = "artifacts/pipeline",
    bucket_size_minutes: Annotated[
        int | None, typer.Option(help="Override bucket size (1, 5, 15).")
    ] = None,
) -> None:
    """Run the full pipeline and persist artifacts."""

    result = run_pipeline_from_files(
        log_path=logs,
        metric_path=metrics,
        config_path=config,
        artifact_root=artifact_root,
        bucket_size_minutes=bucket_size_minutes,
    )
    console.print_json(json.dumps(result.model_dump(mode="json")))


@app.command("print-config")
def print_config(
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
) -> None:
    """Print the loaded runtime configuration."""

    loaded = load_settings_from_yaml(Path(config))
    console.print_json(json.dumps(loaded))


@app.command("list-incidents")
def list_incidents(
    artifact_dir: Annotated[
        str | None,
        typer.Option(help="Full run artifact directory path."),
    ] = None,
    artifact_root: Annotated[
        str, typer.Option(help="Root artifact directory (used with --latest).")
    ] = "artifacts/pipeline",
    latest: Annotated[
        bool, typer.Option(help="Use latest run directory under artifact root.")
    ] = True,
) -> None:
    """List correlated incidents from persisted pipeline artifacts."""

    run_dir = _resolve_run_directory(
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    incidents_path = run_dir / "incidents" / "incidents.json"
    payload = _read_json(incidents_path)
    incidents = payload.get("incidents", [])
    if not isinstance(incidents, list):
        raise typer.BadParameter(f"Invalid incidents payload at {incidents_path}")

    table = Table(title=f"Incidents ({run_dir.name})")
    table.add_column("Incident ID")
    table.add_column("Primary Service")
    table.add_column("Impacted Services")
    table.add_column("Score", justify="right")
    for incident in incidents:
        if not isinstance(incident, dict):
            continue
        table.add_row(
            str(incident.get("incident_id", "n/a")),
            str(incident.get("suspected_primary_service", "n/a")),
            ", ".join(incident.get("impacted_services", [])),
            str(incident.get("correlation_score", "n/a")),
        )
    console.print(table)


@app.command("show-report")
def show_report(
    incident_id: Annotated[str | None, typer.Option(help="Incident ID to display.")] = None,
    index: Annotated[
        int, typer.Option(help="Report index (0-based) when incident_id is not provided.")
    ] = 0,
    artifact_dir: Annotated[
        str | None,
        typer.Option(help="Full run artifact directory path."),
    ] = None,
    artifact_root: Annotated[
        str, typer.Option(help="Root artifact directory (used with --latest).")
    ] = "artifacts/pipeline",
    latest: Annotated[
        bool, typer.Option(help="Use latest run directory under artifact root.")
    ] = True,
) -> None:
    """Show one final report from persisted artifacts."""

    run_dir = _resolve_run_directory(
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    reports_path = run_dir / "reports" / "final_reports.json"
    reports = _load_reports(reports_path)
    report = _select_report(reports, incident_id=incident_id, index=index)
    console.print_json(json.dumps(report))


@app.command("export-report")
def export_report(
    output_path: Annotated[str, typer.Option(help="Output file path (.json, .md, or .html).")],
    incident_id: Annotated[str | None, typer.Option(help="Incident ID to export.")] = None,
    index: Annotated[
        int, typer.Option(help="Report index (0-based) when incident_id is not provided.")
    ] = 0,
    artifact_dir: Annotated[
        str | None,
        typer.Option(help="Full run artifact directory path."),
    ] = None,
    artifact_root: Annotated[
        str, typer.Option(help="Root artifact directory (used with --latest).")
    ] = "artifacts/pipeline",
    latest: Annotated[
        bool, typer.Option(help="Use latest run directory under artifact root.")
    ] = True,
) -> None:
    """Export one final report as JSON, Markdown, or HTML."""

    run_dir = _resolve_run_directory(
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    reports_path = run_dir / "reports" / "final_reports.json"
    reports = _load_reports(reports_path)
    report = FinalIncidentReport.model_validate(
        _select_report(reports, incident_id=incident_id, index=index)
    )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix.lower()
    format_map = {
        ".json": "json",
        ".md": "md",
        ".html": "html",
    }
    output_format = format_map.get(suffix)
    if output_format is None:
        raise typer.BadParameter("output-path must end with .json, .md, or .html")
    target.write_text(
        serialize_report(
            report,
            output_format=cast(ExportFormat, output_format),
        ),
        encoding="utf-8",
    )
    console.print(f"Exported report to {target}")


@app.command("run-eval")
def run_eval_command(
    benchmark_path: Annotated[
        str, typer.Option(help="Path to benchmark scenarios JSON file.")
    ] = "eval/benchmarks/scenarios.json",
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
    artifact_root: Annotated[
        str, typer.Option(help="Root directory for evaluation artifacts.")
    ] = "artifacts/eval",
    include_real_llm: Annotated[
        bool,
        typer.Option(help="Also run real-llm mode (requires openai provider credentials/config)."),
    ] = False,
) -> None:
    """Run evaluation harness across benchmark scenarios."""

    result = run_evaluation(
        benchmark_path=benchmark_path,
        config_path=config,
        artifact_root=artifact_root,
        include_real_llm=include_real_llm,
    )
    console.print_json(json.dumps(result.model_dump(mode="json")))


@app.command("generate-scenario")
def generate_scenario_command(
    scenario_id: Annotated[str, typer.Option(help="Scenario identifier.")],
    scenario_type: Annotated[
        str,
        typer.Option(
            help=(
                "Scenario type: latency_degradation, error_burst, dependency_cascade, "
                "traffic_drop, resource_exhaustion, partial_outage."
            ),
            click_type=click.Choice(
                [
                    "latency_degradation",
                    "error_burst",
                    "dependency_cascade",
                    "traffic_drop",
                    "resource_exhaustion",
                    "partial_outage",
                ],
                case_sensitive=True,
            ),
        ),
    ],
    root_cause_service: Annotated[str, typer.Option(help="Planted root-cause service.")],
    output_dir: Annotated[
        str, typer.Option(help="Directory to write generated logs, metrics, and metadata.")
    ] = "artifacts/generated-scenarios",
    impacted_services: Annotated[
        list[str] | None,
        typer.Option(help="Optional impacted services. Repeat the option to add multiple values."),
    ] = None,
    duration_minutes: Annotated[int, typer.Option(help="Scenario duration in minutes.")] = 30,
    interval_minutes: Annotated[int, typer.Option(help="Sampling interval in minutes.")] = 5,
    seed: Annotated[int, typer.Option(help="Random seed for reproducible generation.")] = 7,
) -> None:
    """Generate one synthetic incident scenario."""

    config = SyntheticScenarioGeneratorConfig(
        scenario_type=cast(SyntheticScenarioType, scenario_type),
        root_cause_service=root_cause_service,
        impacted_services=impacted_services or [],
        duration_minutes=duration_minutes,
        interval_minutes=interval_minutes,
        seed=seed,
    )
    scenario = generate_benchmark_scenario(
        scenario_id=scenario_id,
        description=f"Synthetic {scenario_type} scenario for {root_cause_service}.",
        config=config,
        output_root=output_dir,
    )
    console.print_json(json.dumps(scenario.model_dump(mode="json")))


@app.command("run-demo")
def run_demo_command(
    output_dir: Annotated[
        str, typer.Option(help="Stable output directory for the demo run.")
    ] = "artifacts/demo/portfolio-demo",
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
    include_html: Annotated[bool, typer.Option(help="Also export a polished HTML report.")] = True,
) -> None:
    """Run the deterministic portfolio demo and write stable artifacts."""

    result = run_demo(
        output_root=output_dir,
        config_path=config,
        include_html=include_html,
    )
    console.print_json(json.dumps(result.model_dump(mode="json")))


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


def _resolve_run_directory(
    *,
    artifact_dir: str | None,
    artifact_root: str,
    latest: bool,
) -> Path:
    if artifact_dir:
        path = Path(artifact_dir)
        if not path.exists():
            raise typer.BadParameter(f"Artifact directory not found: {artifact_dir}")
        return path
    if not latest:
        raise typer.BadParameter("Provide --artifact-dir or use --latest")
    root = Path(artifact_root)
    if not root.exists():
        raise typer.BadParameter(f"Artifact root not found: {artifact_root}")
    candidates = [item for item in root.iterdir() if item.is_dir()]
    if not candidates:
        raise typer.BadParameter(f"No run directories found under: {artifact_root}")
    return sorted(candidates)[-1]


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise typer.BadParameter(f"Artifact file not found: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise typer.BadParameter(f"Artifact JSON root must be object: {path}")
    return loaded


def _load_reports(path: Path) -> list[dict[str, object]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise typer.BadParameter(f"Report file must contain a JSON list: {path}")
    reports = [row for row in loaded if isinstance(row, dict)]
    if not reports:
        raise typer.BadParameter(f"No reports found in: {path}")
    return reports


def _select_report(
    reports: list[dict[str, object]],
    *,
    incident_id: str | None,
    index: int,
) -> dict[str, object]:
    if incident_id is not None:
        for report in reports:
            if report.get("incident_id") == incident_id:
                return report
        raise typer.BadParameter(f"Report not found for incident_id={incident_id}")
    if index < 0 or index >= len(reports):
        raise typer.BadParameter(f"Report index out of range: {index}")
    return reports[index]


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


if __name__ == "__main__":
    app()
