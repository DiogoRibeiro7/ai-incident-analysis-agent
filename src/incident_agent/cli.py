"""CLI entrypoints for the incident analysis agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import click
import typer
from rich.console import Console
from rich.table import Table

from incident_agent.core.settings import load_settings_from_yaml, load_webhook_export_config
from incident_agent.eval.runner import (
    compare_evaluation_summaries,
    run_evaluation,
    write_comparison_artifacts,
)
from incident_agent.export.serializers import ExportFormat, serialize_report
from incident_agent.export.webhook import (
    WebhookExportConfig,
    WebhookExportError,
    export_report_via_webhook,
)
from incident_agent.ingestion.logs import ingest_logs
from incident_agent.ingestion.metrics import ingest_metrics
from incident_agent.schemas.eval import (
    EvaluationRegressionThresholds,
    SyntheticScenarioGeneratorConfig,
    SyntheticScenarioType,
)
from incident_agent.schemas.final_report import FinalIncidentReport, ReviewStatus
from incident_agent.services.analyze import analyze_from_files
from incident_agent.services.correlate import correlate_incidents_from_files
from incident_agent.services.demo import run_demo
from incident_agent.services.detect import detect_anomalies_from_files
from incident_agent.services.normalize import normalize_from_files
from incident_agent.services.pipeline import run_pipeline_from_files
from incident_agent.services.rca import run_rca_from_files
from incident_agent.synthetic.generator import generate_benchmark_scenario
from incident_agent.utils.observability import configure_logging
from incident_agent.utils.security import (
    config_security_warnings,
    load_security_config_safe,
    validate_read_path,
    validate_write_path,
)
from incident_agent.workflow.review import transition_report_review

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

    _enforce_read_paths(logs, metrics, config)
    reports = analyze_from_files(log_path=logs, metric_path=metrics, config_path=config)
    serialised = [report.model_dump(mode="json") for report in reports]
    console.print_json(json.dumps(serialised))


@app.command("validate-data")
def validate_data(
    logs: Annotated[str, typer.Option(help="Path to logs file (.jsonl or .csv).")],
    metrics: Annotated[str, typer.Option(help="Path to metrics file (.csv, .json, or .jsonl).")],
) -> None:
    """Validate datasets and print quality metrics."""

    _enforce_read_paths(logs, metrics)
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

    _enforce_read_paths(logs, metrics)
    _enforce_write_path(output_dir)
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
    retrieval_enabled: Annotated[
        bool | None,
        typer.Option(
            "--retrieval-enabled/--no-retrieval-enabled",
            help="Override retrieval setting from config.",
        ),
    ] = None,
    knowledge_source_paths: Annotated[
        list[str] | None,
        typer.Option(help="Optional knowledge source paths (repeat option)."),
    ] = None,
    metrics_source: Annotated[
        str,
        typer.Option(
            help="Metrics source: file or prometheus.",
            click_type=click.Choice(["file", "prometheus"]),
        ),
    ] = "file",
    prometheus_url: Annotated[
        str | None,
        typer.Option(help="Optional Prometheus base URL override."),
    ] = None,
    prometheus_step_seconds: Annotated[
        int | None,
        typer.Option(help="Optional Prometheus query step in seconds."),
    ] = None,
    prometheus_query: Annotated[
        list[str] | None,
        typer.Option(
            help="Prometheus metric query mapping in metric=query format (repeat option)."
        ),
    ] = None,
) -> None:
    """Run the full pipeline and persist artifacts."""

    _enforce_read_paths(logs, metrics, config)
    _enforce_write_path(artifact_root)
    result = run_pipeline_from_files(
        log_path=logs,
        metric_path=metrics,
        config_path=config,
        artifact_root=artifact_root,
        bucket_size_minutes=bucket_size_minutes,
        retrieval_enabled=retrieval_enabled,
        knowledge_source_paths=knowledge_source_paths,
        metrics_source=metrics_source,
        prometheus_url=prometheus_url,
        prometheus_step_seconds=prometheus_step_seconds,
        prometheus_queries=_parse_prometheus_query_flags(prometheus_query),
    )
    console.print_json(json.dumps(result.model_dump(mode="json")))


@app.command("print-config")
def print_config(
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
) -> None:
    """Print the loaded runtime configuration."""

    _enforce_read_paths(config)
    loaded = load_settings_from_yaml(Path(config))
    payload = {"config": loaded, "security_warnings": config_security_warnings(config)}
    console.print_json(json.dumps(payload))


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


@app.command("list-reports")
def list_reports(
    review_status: Annotated[
        ReviewStatus | None,
        typer.Option(
            help="Optional review status filter.",
            click_type=click.Choice(
                ["draft", "reviewed", "approved", "rejected"],
                case_sensitive=True,
            ),
        ),
    ] = None,
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
    """List final reports with optional review status filtering."""

    run_dir = _resolve_run_directory(
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    reports_path = run_dir / "reports" / "final_reports.json"
    reports = _load_reports(reports_path)
    parsed = [FinalIncidentReport.model_validate(item) for item in reports]
    if review_status is not None:
        parsed = [report for report in parsed if report.review_status == review_status]
    serialised = [report.model_dump(mode="json") for report in parsed]
    console.print_json(json.dumps(serialised))


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


@app.command("export-approved-webhook")
def export_approved_webhook(
    destination_url: Annotated[str, typer.Option(help="Webhook destination URL.")],
    incident_id: Annotated[str, typer.Option(help="Incident ID to export.")],
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
    config: Annotated[str, typer.Option(help="Path to YAML config file.")] = "configs/default.yaml",
) -> None:
    """Export one approved report to a generic webhook endpoint."""

    _enforce_read_paths(config)
    run_dir = _resolve_run_directory(
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    reports_path = run_dir / "reports" / "final_reports.json"
    reports = _load_reports(reports_path)
    selected = _select_report(reports, incident_id=incident_id, index=0)
    report = FinalIncidentReport.model_validate(selected)
    config_values = load_webhook_export_config(config)
    webhook_config = WebhookExportConfig(
        timeout_seconds=config_values.timeout_seconds,
        max_retries=config_values.max_retries,
        retry_backoff_seconds=config_values.retry_backoff_seconds,
    )
    try:
        record = export_report_via_webhook(
            report=report,
            destination_url=destination_url,
            audit_log_path=run_dir / "exports" / "webhook_deliveries.jsonl",
            config=webhook_config,
        )
    except WebhookExportError as error:
        raise typer.BadParameter(str(error)) from error
    console.print_json(json.dumps(record.model_dump(mode="json")))


@app.command("mark-reviewed")
def mark_reviewed(
    incident_id: Annotated[str, typer.Option(help="Incident ID to transition.")],
    reviewer: Annotated[str, typer.Option(help="Reviewer identifier.")],
    note: Annotated[str, typer.Option(help="Review note.")],
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
    """Transition report from draft to reviewed."""

    report = _transition_report_from_artifacts(
        incident_id=incident_id,
        to_status="reviewed",
        reviewer=reviewer,
        note=note,
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    console.print_json(json.dumps(report.model_dump(mode="json")))


@app.command("approve-report")
def approve_report(
    incident_id: Annotated[str, typer.Option(help="Incident ID to transition.")],
    reviewer: Annotated[str, typer.Option(help="Reviewer identifier.")],
    note: Annotated[str, typer.Option(help="Approval note.")],
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
    """Transition report from reviewed to approved."""

    report = _transition_report_from_artifacts(
        incident_id=incident_id,
        to_status="approved",
        reviewer=reviewer,
        note=note,
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    console.print_json(json.dumps(report.model_dump(mode="json")))


@app.command("reject-report")
def reject_report(
    incident_id: Annotated[str, typer.Option(help="Incident ID to transition.")],
    reviewer: Annotated[str, typer.Option(help="Reviewer identifier.")],
    note: Annotated[str, typer.Option(help="Rejection note.")],
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
    """Transition report from reviewed to rejected."""

    report = _transition_report_from_artifacts(
        incident_id=incident_id,
        to_status="rejected",
        reviewer=reviewer,
        note=note,
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    console.print_json(json.dumps(report.model_dump(mode="json")))


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

    _enforce_read_paths(benchmark_path, config)
    _enforce_write_path(artifact_root)
    result = run_evaluation(
        benchmark_path=benchmark_path,
        config_path=config,
        artifact_root=artifact_root,
        include_real_llm=include_real_llm,
    )
    console.print_json(json.dumps(result.model_dump(mode="json")))


@app.command("compare-eval")
def compare_eval_command(
    baseline_summary_path: Annotated[
        str, typer.Option(help="Path to baseline summary.json artifact.")
    ],
    candidate_summary_path: Annotated[
        str, typer.Option(help="Path to candidate summary.json artifact.")
    ],
    output_dir: Annotated[
        str, typer.Option(help="Directory for comparison artifacts.")
    ] = "artifacts/eval/compare",
    root_cause_drop_max: Annotated[
        float, typer.Option(help="Allowed root-cause correctness drop.")
    ] = 0.02,
    impacted_drop_max: Annotated[
        float, typer.Option(help="Allowed impacted-service correctness drop.")
    ] = 0.02,
    grounding_drop_max: Annotated[
        float, typer.Option(help="Allowed factual grounding drop.")
    ] = 0.02,
    citation_coverage_drop_max: Annotated[
        float, typer.Option(help="Allowed claim citation coverage drop.")
    ] = 0.02,
    completeness_drop_max: Annotated[
        float, typer.Option(help="Allowed report completeness drop.")
    ] = 0.02,
    hallucination_increase_max: Annotated[
        float, typer.Option(help="Allowed hallucination rate increase.")
    ] = 0.05,
) -> None:
    """Compare baseline vs candidate eval summaries and fail on regressions."""

    _enforce_read_paths(baseline_summary_path, candidate_summary_path)
    _enforce_write_path(output_dir)
    thresholds = EvaluationRegressionThresholds(
        root_cause_correctness_drop_max=root_cause_drop_max,
        impacted_service_correctness_drop_max=impacted_drop_max,
        factual_grounding_drop_max=grounding_drop_max,
        citation_coverage_drop_max=citation_coverage_drop_max,
        report_completeness_drop_max=completeness_drop_max,
        hallucination_rate_increase_max=hallucination_increase_max,
    )
    comparison = compare_evaluation_summaries(
        baseline_summary_path=baseline_summary_path,
        candidate_summary_path=candidate_summary_path,
        thresholds=thresholds,
    )
    write_comparison_artifacts(output_dir=output_dir, comparison=comparison)
    console.print_json(json.dumps(comparison.model_dump(mode="json")))
    if not comparison.passed:
        raise typer.Exit(code=1)


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

    _enforce_read_paths(config)
    _enforce_write_path(output_dir)
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
    if not path.exists():
        raise typer.BadParameter(f"Report file not found: {path}")
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


def _parse_prometheus_query_flags(values: list[str] | None) -> dict[str, str] | None:
    if values is None:
        return None
    parsed: dict[str, str] = {}
    for value in values:
        metric_name, separator, query = value.partition("=")
        if not separator or not metric_name.strip() or not query.strip():
            raise typer.BadParameter(
                "Each --prometheus-query must be in metric_name=query format."
            )
        parsed[metric_name.strip()] = query.strip()
    return parsed


def _transition_report_from_artifacts(
    *,
    incident_id: str,
    to_status: ReviewStatus,
    reviewer: str,
    note: str,
    artifact_dir: str | None,
    artifact_root: str,
    latest: bool,
) -> FinalIncidentReport:
    run_dir = _resolve_run_directory(
        artifact_dir=artifact_dir,
        artifact_root=artifact_root,
        latest=latest,
    )
    reports_path = run_dir / "reports" / "final_reports.json"
    reports = _load_reports(reports_path)
    parsed = [FinalIncidentReport.model_validate(item) for item in reports]

    match: FinalIncidentReport | None = None
    for report in parsed:
        if report.incident_id == incident_id:
            match = report
            break
    if match is None:
        raise typer.BadParameter(f"Report not found for incident_id={incident_id}")

    try:
        transition_report_review(
            match,
            to_status=to_status,
            reviewer=reviewer,
            note=note,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    reports_path.write_text(
        json.dumps([report.model_dump(mode="json") for report in parsed], indent=2),
        encoding="utf-8",
    )
    return match


def _enforce_read_paths(*paths: str) -> None:
    workspace_root = Path.cwd()
    policy = load_security_config_safe("configs/default.yaml")
    for value in paths:
        validate_read_path(value, config=policy, workspace_root=workspace_root)


def _enforce_write_path(path: str) -> None:
    workspace_root = Path.cwd()
    policy = load_security_config_safe("configs/default.yaml")
    validate_write_path(path, config=policy, workspace_root=workspace_root)


if __name__ == "__main__":
    app()
