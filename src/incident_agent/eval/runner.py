"""Evaluation runner for benchmark scenarios."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter

import yaml

from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.eval.benchmarks import load_benchmark_scenarios
from incident_agent.schemas.eval import (
    BenchmarkScenario,
    EvaluationMetrics,
    EvaluationResult,
    EvaluationRunRecord,
    EvaluationSummary,
)
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.services.pipeline import run_pipeline_from_files
from incident_agent.services.rca import run_rca_from_files


def run_evaluation(
    *,
    benchmark_path: str = "eval/benchmarks/scenarios.json",
    config_path: str = "configs/default.yaml",
    artifact_root: str = "artifacts/eval",
    include_real_llm: bool = False,
) -> EvaluationResult:
    """Run evaluation benchmarks across heuristic, mock, and optional real LLM modes."""

    scenarios = load_benchmark_scenarios(benchmark_path)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(artifact_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    modes = ["heuristic-only", "mock-llm"]
    if include_real_llm:
        modes.append("real-llm")

    records: list[EvaluationRunRecord] = []
    for scenario in scenarios:
        for mode in modes:
            record = _evaluate_scenario_mode(
                scenario=scenario,
                mode=mode,
                config_path=config_path,
                run_dir=run_dir,
            )
            records.append(record)

    summaries = _summarize_records(records)
    result = EvaluationResult(
        run_id=run_id,
        artifact_dir=str(run_dir),
        records=records,
        summaries=summaries,
    )
    _write_artifacts(run_dir=run_dir, result=result)
    return result


def _evaluate_scenario_mode(
    *,
    scenario: BenchmarkScenario,
    mode: str,
    config_path: str,
    run_dir: Path,
) -> EvaluationRunRecord:
    start = perf_counter()
    try:
        if mode == "heuristic-only":
            (
                report,
                predicted_root,
                impacted_services,
                incident_count,
                token_usage,
                estimated_cost,
            ) = _run_heuristic_mode(
                scenario=scenario,
                config_path=config_path,
            )
        elif mode == "mock-llm":
            (
                report,
                predicted_root,
                impacted_services,
                incident_count,
                token_usage,
                estimated_cost,
            ) = _run_pipeline_mode(
                scenario=scenario,
                config_path=config_path,
                run_dir=run_dir,
                provider="mock",
            )
        else:
            (
                report,
                predicted_root,
                impacted_services,
                incident_count,
                token_usage,
                estimated_cost,
            ) = _run_pipeline_mode(
                scenario=scenario,
                config_path=config_path,
                run_dir=run_dir,
                provider="openai",
            )
    except Exception as error:
        latency = perf_counter() - start
        metrics = EvaluationMetrics(
            root_cause_correctness=0.0,
            impacted_service_correctness=0.0,
            factual_grounding=0.0,
            hallucination_rate=1.0,
            report_completeness=0.0,
            latency_seconds=round(latency, 4),
            token_usage=None,
            estimated_cost_usd=None,
        )
        return EvaluationRunRecord(
            scenario_id=scenario.scenario_id,
            mode=mode,
            success=False,
            error=str(error),
            incident_count=0,
            metrics=metrics,
        )

    latency = perf_counter() - start
    metrics = _score_report(
        scenario=scenario,
        report=report,
        predicted_root=predicted_root,
        impacted_services=impacted_services,
        latency_seconds=latency,
        token_usage=token_usage,
        estimated_cost_usd=estimated_cost,
    )
    return EvaluationRunRecord(
        scenario_id=scenario.scenario_id,
        mode=mode,
        success=True,
        predicted_root_cause=predicted_root,
        predicted_impacted_services=impacted_services,
        incident_count=incident_count,
        metrics=metrics,
    )


def _run_heuristic_mode(
    *,
    scenario: BenchmarkScenario,
    config_path: str,
) -> tuple[FinalIncidentReport, str | None, list[str], int, int | None, float | None]:
    rca = run_rca_from_files(
        log_path=scenario.logs_path,
        metric_path=scenario.metrics_path,
        config_path=config_path,
        bucket_size_minutes=5,
    )
    if not rca.hypotheses:
        report = FinalIncidentReport(
            incident_id=f"{scenario.scenario_id}-none",
            incident_summary="No incident candidate identified.",
            root_cause_explanation="No root-cause hypothesis generated.",
            executive_summary="No significant incident detected for this scenario.",
            engineering_handoff="No engineering handoff required.",
            remediation_suggestions=["Monitor baseline and verify detector thresholds."],
            facts=[],
            inferences=[],
            uncertainties=["No incidents were produced by correlation and RCA."],
        )
        return report, None, [], 0, None, None

    hypothesis = rca.hypotheses[0]
    summary = rca.summaries[0]
    report = FinalIncidentReport(
        incident_id=hypothesis.incident_id,
        incident_summary="Heuristic RCA indicates an incident affecting service health.",
        root_cause_explanation=(
            f"Most likely root cause is {hypothesis.suspected_root_cause_service} "
            f"(confidence {hypothesis.confidence_score:.2f})."
        ),
        executive_summary="Incident detected and triaged using deterministic heuristics.",
        engineering_handoff=hypothesis.rationale,
        remediation_suggestions=[
            "Inspect service dependencies",
            "Review recent configuration changes",
        ],
        facts=[
            f"Impacted services: {', '.join(summary.impacted_services)}",
            f"Total evidence: {summary.total_evidence}",
        ],
        inferences=[hypothesis.rationale],
        uncertainties=hypothesis.unresolved_ambiguities,
    )
    return (
        report,
        hypothesis.suspected_root_cause_service,
        summary.impacted_services,
        len(rca.hypotheses),
        None,
        None,
    )


def _run_pipeline_mode(
    *,
    scenario: BenchmarkScenario,
    config_path: str,
    run_dir: Path,
    provider: str,
) -> tuple[FinalIncidentReport, str | None, list[str], int, int | None, float | None]:
    effective_config = _write_config_with_provider(
        config_path=config_path,
        provider=provider,
        target=run_dir / f"config.{provider}.{scenario.scenario_id}.yaml",
    )
    result = run_pipeline_from_files(
        log_path=scenario.logs_path,
        metric_path=scenario.metrics_path,
        config_path=str(effective_config),
        artifact_root=str(run_dir / "pipeline-runs"),
        bucket_size_minutes=5,
    )
    if not result.final_reports:
        report = FinalIncidentReport(
            incident_id=f"{scenario.scenario_id}-none",
            incident_summary="No final report generated.",
            root_cause_explanation="No root-cause explanation generated.",
            executive_summary="Pipeline did not produce report output.",
            engineering_handoff="No handoff available.",
            remediation_suggestions=["Verify scenario data and pipeline thresholds."],
            facts=[],
            inferences=[],
            uncertainties=["No final reports were generated for this run."],
        )
        return (
            report,
            None,
            [],
            result.incident_count,
            result.llm_usage.total_tokens,
            result.llm_usage.total_estimated_cost_usd,
        )

    report = result.final_reports[0]
    return (
        report,
        _extract_root_service(report),
        _extract_impacted_services(report),
        result.incident_count,
        result.llm_usage.total_tokens,
        result.llm_usage.total_estimated_cost_usd,
    )


def _write_config_with_provider(*, config_path: str, provider: str, target: Path) -> Path:
    loaded = load_settings_from_yaml(Path(config_path))
    llm_section = loaded.get("llm", {})
    if not isinstance(llm_section, dict):
        llm_section = {}
    llm_section["provider"] = provider
    loaded["llm"] = llm_section
    target.write_text(yaml.safe_dump(loaded, sort_keys=False), encoding="utf-8")
    return target


def _extract_root_service(report: FinalIncidentReport) -> str | None:
    text = report.root_cause_explanation.lower()
    for token in ["checkout-service", "api-service", "gateway-service", "worker-service"]:
        if token in text:
            return token
    return None


def _extract_impacted_services(report: FinalIncidentReport) -> list[str]:
    pool = {"checkout-service", "api-service", "gateway-service", "worker-service"}
    text = " ".join(
        [
            report.incident_summary,
            report.root_cause_explanation,
            report.executive_summary,
            report.engineering_handoff,
            " ".join(report.facts),
        ]
    ).lower()
    services = sorted(service for service in pool if service in text)
    return services


def _score_report(
    *,
    scenario: BenchmarkScenario,
    report: FinalIncidentReport,
    predicted_root: str | None,
    impacted_services: list[str],
    latency_seconds: float,
    token_usage: int | None,
    estimated_cost_usd: float | None,
) -> EvaluationMetrics:
    expected_root = scenario.expected_root_cause
    root_correct = 1.0 if expected_root is not None and predicted_root == expected_root else 0.0
    expected_impacted = set(scenario.expected_impacted_services)
    predicted_impacted = set(impacted_services)
    if not expected_impacted and not predicted_impacted:
        impacted_score = 1.0
    else:
        impacted_score = len(expected_impacted & predicted_impacted) / max(
            len(expected_impacted | predicted_impacted), 1
        )

    known_services = set(scenario.expected_impacted_services)
    if scenario.expected_root_cause:
        known_services.add(scenario.expected_root_cause)
    text = " ".join(
        [
            report.incident_summary,
            report.root_cause_explanation,
            report.executive_summary,
            report.engineering_handoff,
            " ".join(report.facts),
            " ".join(report.inferences),
        ]
    ).lower()
    service_tokens = [
        "checkout-service",
        "api-service",
        "gateway-service",
        "worker-service",
    ]
    mentioned_services = {service for service in service_tokens if service in text}
    hallucinated = {service for service in mentioned_services if service not in known_services}
    hallucination_rate = (
        len(hallucinated) / max(len(mentioned_services), 1) if mentioned_services else 0.0
    )
    factual_grounding = max(0.0, 1.0 - hallucination_rate)

    completeness_fields = [
        bool(report.incident_summary.strip()),
        bool(report.root_cause_explanation.strip()),
        bool(report.executive_summary.strip()),
        bool(report.engineering_handoff.strip()),
        bool(report.remediation_suggestions),
    ]
    completeness = sum(1 for flag in completeness_fields if flag) / len(completeness_fields)
    return EvaluationMetrics(
        root_cause_correctness=round(root_correct, 4),
        impacted_service_correctness=round(impacted_score, 4),
        factual_grounding=round(factual_grounding, 4),
        hallucination_rate=round(hallucination_rate, 4),
        report_completeness=round(completeness, 4),
        latency_seconds=round(latency_seconds, 4),
        token_usage=token_usage,
        estimated_cost_usd=estimated_cost_usd,
    )


def _summarize_records(records: list[EvaluationRunRecord]) -> list[EvaluationSummary]:
    modes = sorted({record.mode for record in records})
    summaries: list[EvaluationSummary] = []
    for mode in modes:
        scoped = [record for record in records if record.mode == mode]
        successful = [record for record in scoped if record.success]
        if not scoped:
            continue
        if successful:
            summary = EvaluationSummary(
                mode=mode,
                runs=len(scoped),
                success_rate=round(len(successful) / len(scoped), 4),
                root_cause_correctness=round(
                    mean(item.metrics.root_cause_correctness for item in successful), 4
                ),
                impacted_service_correctness=round(
                    mean(item.metrics.impacted_service_correctness for item in successful), 4
                ),
                factual_grounding=round(
                    mean(item.metrics.factual_grounding for item in successful),
                    4,
                ),
                hallucination_rate=round(
                    mean(item.metrics.hallucination_rate for item in successful),
                    4,
                ),
                report_completeness=round(
                    mean(item.metrics.report_completeness for item in successful), 4
                ),
                latency_seconds=round(mean(item.metrics.latency_seconds for item in successful), 4),
                average_token_usage=round(
                    mean(
                        item.metrics.token_usage
                        for item in successful
                        if item.metrics.token_usage is not None
                    ),
                    2,
                )
                if any(item.metrics.token_usage is not None for item in successful)
                else None,
                total_estimated_cost_usd=round(
                    sum(item.metrics.estimated_cost_usd or 0.0 for item in successful),
                    8,
                ),
            )
        else:
            summary = EvaluationSummary(
                mode=mode,
                runs=len(scoped),
                success_rate=0.0,
                root_cause_correctness=0.0,
                impacted_service_correctness=0.0,
                factual_grounding=0.0,
                hallucination_rate=1.0,
                report_completeness=0.0,
                latency_seconds=0.0,
                average_token_usage=None,
                total_estimated_cost_usd=None,
            )
        summaries.append(summary)
    return summaries


def _write_artifacts(*, run_dir: Path, result: EvaluationResult) -> None:
    (run_dir / "records.json").write_text(
        json.dumps([record.model_dump(mode="json") for record in result.records], indent=2),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps([summary.model_dump(mode="json") for summary in result.summaries], indent=2),
        encoding="utf-8",
    )
    markdown = _summary_markdown(result)
    (run_dir / "summary.md").write_text(markdown, encoding="utf-8")


def _summary_markdown(result: EvaluationResult) -> str:
    header = (
        "# Evaluation Summary\n\n"
        f"Run ID: `{result.run_id}`\n\n"
        "| Mode | Runs | Success | Root Cause | Impacted Services | Grounding "
        "| Hallucination | Completeness | Latency (s) | Avg Tokens | Total Cost (USD) |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    lines = []
    for summary in result.summaries:
        avg_tokens = (
            summary.average_token_usage
            if summary.average_token_usage is not None
            else "n/a"
        )
        total_cost = (
            summary.total_estimated_cost_usd
            if summary.total_estimated_cost_usd is not None
            else "n/a"
        )
        lines.append(
            "| "
            f"{summary.mode} | {summary.runs} | {summary.success_rate:.2f} | "
            f"{summary.root_cause_correctness:.2f} | {summary.impacted_service_correctness:.2f} | "
            f"{summary.factual_grounding:.2f} | {summary.hallucination_rate:.2f} | "
            f"{summary.report_completeness:.2f} | {summary.latency_seconds:.2f} | "
            f"{avg_tokens} | {total_cost} |"
        )
    return header + "\n".join(lines) + "\n"
