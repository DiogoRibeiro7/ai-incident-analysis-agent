"""Evaluation runner for benchmark scenarios."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import NamedTuple

import yaml

from incident_agent.core.settings import load_grounding_config, load_settings_from_yaml
from incident_agent.eval.benchmarks import load_benchmark_scenarios
from incident_agent.grounding.validate import validate_report_grounding
from incident_agent.schemas.eval import (
    BenchmarkScenario,
    EvaluationComparisonFinding,
    EvaluationComparisonResult,
    EvaluationMetrics,
    EvaluationMode,
    EvaluationRegressionThresholds,
    EvaluationResult,
    EvaluationRunRecord,
    EvaluationSummary,
    evaluation_modes,
)
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.schemas.grounding import ClaimType, ClaimValidationStatus, GroundingSummary
from incident_agent.services.pipeline import run_pipeline_from_files
from incident_agent.services.rca import run_rca_from_files


class ClaimGroundingMetricValues(NamedTuple):
    factual_claim_count: int
    supported_factual_claim_count: int
    unsupported_factual_claim_count: int
    contradictory_factual_claim_count: int
    factual_claim_support_rate: float
    unsupported_factual_claim_rate: float
    contradictory_factual_claim_rate: float


class IncidentDetectionCounts(NamedTuple):
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int


_ANOMALY_KEYWORDS: dict[str, set[str]] = {
    "latency_spike": {"latency", "slow", "slowness", "p95", "response"},
    "error_rate_spike": {"error", "errors", "exception", "5xx", "failure", "failures"},
    "cpu_anomaly": {"cpu"},
    "memory_anomaly": {"memory"},
    "traffic_drop": {"traffic", "request", "requests", "drop", "dropped", "disappeared"},
    "error_log_burst": {"error", "errors", "log", "logs", "burst"},
    "critical_log_burst": {"critical", "log", "logs", "burst"},
    "service_unavailability": {
        "availability",
        "unavailable",
        "unavailability",
        "outage",
        "heartbeat",
        "down",
    },
}


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

    modes = evaluation_modes(include_real_llm=include_real_llm)

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
    mode: EvaluationMode,
    config_path: str,
    run_dir: Path,
) -> EvaluationRunRecord:
    start = perf_counter()
    try:
        if mode is EvaluationMode.HEURISTIC_ONLY:
            (
                report,
                predicted_root,
                impacted_services,
                anomaly_types,
                incident_count,
                token_usage,
                estimated_cost,
                grounding_summary,
            ) = _run_heuristic_mode(
                scenario=scenario,
                config_path=config_path,
            )
        elif mode is EvaluationMode.MOCK_LLM_NO_RETRIEVAL:
            (
                report,
                predicted_root,
                impacted_services,
                anomaly_types,
                incident_count,
                token_usage,
                estimated_cost,
                grounding_summary,
            ) = _run_pipeline_mode(
                scenario=scenario,
                config_path=config_path,
                run_dir=run_dir,
                provider="mock",
                retrieval_enabled=False,
            )
        elif mode is EvaluationMode.MOCK_LLM_RETRIEVAL:
            (
                report,
                predicted_root,
                impacted_services,
                anomaly_types,
                incident_count,
                token_usage,
                estimated_cost,
                grounding_summary,
            ) = _run_pipeline_mode(
                scenario=scenario,
                config_path=config_path,
                run_dir=run_dir,
                provider="mock",
                retrieval_enabled=True,
            )
        elif mode is EvaluationMode.REAL_LLM_NO_RETRIEVAL:
            (
                report,
                predicted_root,
                impacted_services,
                anomaly_types,
                incident_count,
                token_usage,
                estimated_cost,
                grounding_summary,
            ) = _run_pipeline_mode(
                scenario=scenario,
                config_path=config_path,
                run_dir=run_dir,
                provider="openai",
                retrieval_enabled=False,
            )
        elif mode is EvaluationMode.REAL_LLM_RETRIEVAL:
            (
                report,
                predicted_root,
                impacted_services,
                anomaly_types,
                incident_count,
                token_usage,
                estimated_cost,
                grounding_summary,
            ) = _run_pipeline_mode(
                scenario=scenario,
                config_path=config_path,
                run_dir=run_dir,
                provider="openai",
                retrieval_enabled=True,
            )
        else:
            raise ValueError(f"Unsupported evaluation mode: {mode}")
    except Exception as error:
        latency = perf_counter() - start
        incident_counts = _incident_detection_counts(scenario=scenario, incident_count=0)
        metrics = EvaluationMetrics(
            incident_detected=False,
            incident_expectation_correctness=1.0 if not scenario.incident_expected else 0.0,
            incident_count_correctness=_incident_count_correctness(
                scenario=scenario,
                incident_count=0,
            ),
            incident_true_positive=incident_counts.true_positive,
            incident_false_positive=incident_counts.false_positive,
            incident_false_negative=incident_counts.false_negative,
            incident_true_negative=incident_counts.true_negative,
            root_cause_correctness=0.0,
            impacted_service_correctness=0.0,
            impacted_service_precision=0.0,
            impacted_service_recall=0.0,
            impacted_service_f1=0.0,
            anomaly_type_recall=0.0,
            service_entity_precision=0.0,
            unexpected_service_mention_rate=1.0,
            citation_coverage=0.0,
            retrieval_relevance=0.0,
            factual_claim_count=0,
            supported_factual_claim_count=0,
            unsupported_factual_claim_count=0,
            contradictory_factual_claim_count=0,
            factual_claim_support_rate=0.0,
            unsupported_factual_claim_rate=0.0,
            contradictory_factual_claim_rate=0.0,
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
        anomaly_types=anomaly_types,
        incident_count=incident_count,
        mode=mode,
        grounding_summary=grounding_summary,
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
        predicted_anomaly_types=anomaly_types,
        incident_count=incident_count,
        metrics=metrics,
    )


def _run_heuristic_mode(
    *,
    scenario: BenchmarkScenario,
    config_path: str,
) -> tuple[
    FinalIncidentReport,
    str | None,
    list[str],
    list[str],
    int,
    int | None,
    float | None,
    GroundingSummary | None,
]:
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
        return report, None, [], [], 0, None, None, None

    hypothesis = rca.hypotheses[0]
    summary = rca.summaries[0]
    anomaly_types = sorted(summary.anomaly_type_counts)
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
            f"Anomaly types: {', '.join(anomaly_types)}",
            f"Total evidence: {summary.total_evidence}",
        ],
        inferences=[hypothesis.rationale],
        uncertainties=hypothesis.unresolved_ambiguities,
    )
    grounding_summary = validate_report_grounding(
        report=report,
        evidence_bundle=rca.bundles[0],
        root_cause_hypothesis=hypothesis,
        retrieved_context=[],
        config=load_grounding_config(config_path),
    )
    return (
        report,
        hypothesis.suspected_root_cause_service,
        summary.impacted_services,
        anomaly_types,
        len(rca.hypotheses),
        None,
        None,
        grounding_summary,
    )


def _run_pipeline_mode(
    *,
    scenario: BenchmarkScenario,
    config_path: str,
    run_dir: Path,
    provider: str,
    retrieval_enabled: bool,
) -> tuple[
    FinalIncidentReport,
    str | None,
    list[str],
    list[str],
    int,
    int | None,
    float | None,
    GroundingSummary | None,
]:
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
        retrieval_enabled=retrieval_enabled,
        knowledge_source_paths=(
            scenario.retrieval_source_paths
            if retrieval_enabled and scenario.retrieval_source_paths
            else (
                ["data/knowledge/runbooks", "data/knowledge/incidents"]
                if retrieval_enabled
                else None
            )
        ),
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
            [],
            result.incident_count,
            result.llm_usage.total_tokens,
            result.llm_usage.total_estimated_cost_usd,
            None,
        )

    report = result.final_reports[0]
    grounding_summary = next(
        (item for item in result.grounding_summaries if item.incident_id == report.incident_id),
        None,
    )
    return (
        report,
        _extract_root_service(report),
        _extract_impacted_services(report),
        _extract_anomaly_types(report),
        result.incident_count,
        result.llm_usage.total_tokens,
        result.llm_usage.total_estimated_cost_usd,
        grounding_summary,
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


def _extract_anomaly_types(report: FinalIncidentReport) -> list[str]:
    text = " ".join(
        [
            report.incident_summary,
            report.root_cause_explanation,
            report.executive_summary,
            report.engineering_handoff,
            " ".join(report.facts),
            " ".join(report.inferences),
            " ".join(report.uncertainties),
        ]
    ).lower()
    tokens = set(text.replace("_", " ").replace("-", " ").split())
    anomaly_types = [
        anomaly_type
        for anomaly_type, keywords in _ANOMALY_KEYWORDS.items()
        if anomaly_type in text or tokens & keywords
    ]
    return anomaly_types


def _score_report(
    *,
    scenario: BenchmarkScenario,
    report: FinalIncidentReport,
    predicted_root: str | None,
    impacted_services: list[str],
    anomaly_types: list[str],
    incident_count: int,
    mode: EvaluationMode,
    grounding_summary: GroundingSummary | None,
    latency_seconds: float,
    token_usage: int | None,
    estimated_cost_usd: float | None,
) -> EvaluationMetrics:
    expected_root = scenario.expected_root_cause
    allowed_roots = set(scenario.allowed_root_causes)
    if expected_root is not None:
        allowed_roots.add(expected_root)
    if not scenario.incident_expected:
        root_correct = 1.0 if predicted_root is None else 0.0
    else:
        root_correct = (
            1.0 if predicted_root is not None and predicted_root in allowed_roots else 0.0
        )

    incident_detected = incident_count > 0
    incident_expectation = 1.0 if incident_detected == scenario.incident_expected else 0.0
    incident_count_score = _incident_count_correctness(
        scenario=scenario,
        incident_count=incident_count,
    )
    incident_counts = _incident_detection_counts(
        scenario=scenario,
        incident_count=incident_count,
    )

    expected_impacted = set(scenario.expected_impacted_services)
    predicted_impacted = set(impacted_services)
    if not expected_impacted and not predicted_impacted:
        impacted_score = 1.0
    else:
        impacted_score = len(expected_impacted & predicted_impacted) / max(
            len(expected_impacted | predicted_impacted), 1
        )
    impacted_precision, impacted_recall, impacted_f1 = _precision_recall_f1(
        expected=expected_impacted,
        predicted=predicted_impacted,
    )

    expected_anomaly_types = set(scenario.expected_anomaly_types)
    predicted_anomaly_types = set(anomaly_types)
    anomaly_type_recall = (
        len(expected_anomaly_types & predicted_anomaly_types) / len(expected_anomaly_types)
        if expected_anomaly_types
        else 1.0
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
    unexpected_services = {
        service for service in mentioned_services if service not in known_services
    }
    unexpected_service_mention_rate = (
        len(unexpected_services) / max(len(mentioned_services), 1) if mentioned_services else 0.0
    )
    service_entity_precision = max(0.0, 1.0 - unexpected_service_mention_rate)
    claim_metrics = _claim_grounding_metrics(grounding_summary)

    completeness_fields = [
        bool(report.incident_summary.strip()),
        bool(report.root_cause_explanation.strip()),
        bool(report.executive_summary.strip()),
        bool(report.engineering_handoff.strip()),
        bool(report.remediation_suggestions),
    ]
    completeness = sum(1 for flag in completeness_fields if flag) / len(completeness_fields)
    citation_claims = report.claim_citations
    citation_coverage = (
        sum(1 for item in citation_claims if item.support_ids) / len(citation_claims)
        if citation_claims
        else 0.0
    )
    retrieval_relevance = 0.0
    if mode in (EvaluationMode.MOCK_LLM_RETRIEVAL, EvaluationMode.REAL_LLM_RETRIEVAL):
        retrieved_ids = set(report.citations)
        used_retrieved_ids: set[str] = set()
        for item in citation_claims:
            for support_id in item.support_ids:
                if support_id in retrieved_ids:
                    used_retrieved_ids.add(support_id)
        retrieval_relevance = len(used_retrieved_ids) / len(retrieved_ids) if retrieved_ids else 0.0
    return EvaluationMetrics(
        incident_detected=incident_detected,
        incident_expectation_correctness=round(incident_expectation, 4),
        incident_count_correctness=round(incident_count_score, 4),
        incident_true_positive=incident_counts.true_positive,
        incident_false_positive=incident_counts.false_positive,
        incident_false_negative=incident_counts.false_negative,
        incident_true_negative=incident_counts.true_negative,
        root_cause_correctness=round(root_correct, 4),
        impacted_service_correctness=round(impacted_score, 4),
        impacted_service_precision=round(impacted_precision, 4),
        impacted_service_recall=round(impacted_recall, 4),
        impacted_service_f1=round(impacted_f1, 4),
        anomaly_type_recall=round(anomaly_type_recall, 4),
        service_entity_precision=round(service_entity_precision, 4),
        unexpected_service_mention_rate=round(unexpected_service_mention_rate, 4),
        citation_coverage=round(citation_coverage, 4),
        retrieval_relevance=round(retrieval_relevance, 4),
        factual_claim_count=claim_metrics.factual_claim_count,
        supported_factual_claim_count=claim_metrics.supported_factual_claim_count,
        unsupported_factual_claim_count=claim_metrics.unsupported_factual_claim_count,
        contradictory_factual_claim_count=claim_metrics.contradictory_factual_claim_count,
        factual_claim_support_rate=claim_metrics.factual_claim_support_rate,
        unsupported_factual_claim_rate=claim_metrics.unsupported_factual_claim_rate,
        contradictory_factual_claim_rate=claim_metrics.contradictory_factual_claim_rate,
        report_completeness=round(completeness, 4),
        latency_seconds=round(latency_seconds, 4),
        token_usage=token_usage,
        estimated_cost_usd=estimated_cost_usd,
    )


def _claim_grounding_metrics(
    grounding_summary: GroundingSummary | None,
) -> ClaimGroundingMetricValues:
    if grounding_summary is None:
        return ClaimGroundingMetricValues(
            factual_claim_count=0,
            supported_factual_claim_count=0,
            unsupported_factual_claim_count=0,
            contradictory_factual_claim_count=0,
            factual_claim_support_rate=0.0,
            unsupported_factual_claim_rate=0.0,
            contradictory_factual_claim_rate=0.0,
        )

    factual_claims = [
        item for item in grounding_summary.claims if item.claim_type is ClaimType.FACT
    ]
    factual_claim_count = len(factual_claims)
    supported = sum(1 for item in factual_claims if item.status is ClaimValidationStatus.SUPPORTED)
    unsupported = sum(
        1 for item in factual_claims if item.status is ClaimValidationStatus.UNSUPPORTED
    )
    contradictory = sum(
        1 for item in factual_claims if item.status is ClaimValidationStatus.CONTRADICTORY
    )
    if factual_claim_count == 0:
        support_rate = 0.0
        unsupported_rate = 0.0
        contradictory_rate = 0.0
    else:
        support_rate = supported / factual_claim_count
        unsupported_rate = unsupported / factual_claim_count
        contradictory_rate = contradictory / factual_claim_count
    return ClaimGroundingMetricValues(
        factual_claim_count=factual_claim_count,
        supported_factual_claim_count=supported,
        unsupported_factual_claim_count=unsupported,
        contradictory_factual_claim_count=contradictory,
        factual_claim_support_rate=round(support_rate, 4),
        unsupported_factual_claim_rate=round(unsupported_rate, 4),
        contradictory_factual_claim_rate=round(contradictory_rate, 4),
    )


def _precision_recall_f1(*, expected: set[str], predicted: set[str]) -> tuple[float, float, float]:
    if not expected and not predicted:
        return 1.0, 1.0, 1.0
    true_positive = len(expected & predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 1.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _incident_count_correctness(*, scenario: BenchmarkScenario, incident_count: int) -> float:
    if not scenario.incident_expected:
        return 1.0 if incident_count == 0 else 0.0
    if (
        scenario.expected_max_incidents is not None
        and incident_count > scenario.expected_max_incidents
    ):
        return 0.0
    if incident_count < scenario.expected_min_incidents:
        return 0.0
    return 1.0


def _incident_detection_counts(
    *,
    scenario: BenchmarkScenario,
    incident_count: int,
) -> IncidentDetectionCounts:
    detected = incident_count > 0
    return IncidentDetectionCounts(
        true_positive=1 if scenario.incident_expected and detected else 0,
        false_positive=1 if not scenario.incident_expected and detected else 0,
        false_negative=1 if scenario.incident_expected and not detected else 0,
        true_negative=1 if not scenario.incident_expected and not detected else 0,
    )


def _summarize_records(records: list[EvaluationRunRecord]) -> list[EvaluationSummary]:
    mode_order = {mode: index for index, mode in enumerate(evaluation_modes(include_real_llm=True))}
    modes = sorted(
        {record.mode for record in records},
        key=lambda mode: mode_order.get(mode, len(mode_order)),
    )
    summaries: list[EvaluationSummary] = []
    for mode in modes:
        scoped = [record for record in records if record.mode == mode]
        successful = [record for record in scoped if record.success]
        if not scoped:
            continue
        incident_true_positive = sum(item.metrics.incident_true_positive for item in scoped)
        incident_false_positive = sum(item.metrics.incident_false_positive for item in scoped)
        incident_false_negative = sum(item.metrics.incident_false_negative for item in scoped)
        incident_true_negative = sum(item.metrics.incident_true_negative for item in scoped)
        incident_precision = incident_true_positive / max(
            incident_true_positive + incident_false_positive,
            1,
        )
        incident_recall = incident_true_positive / max(
            incident_true_positive + incident_false_negative,
            1,
        )
        incident_f1 = (
            0.0
            if incident_precision + incident_recall == 0
            else 2 * incident_precision * incident_recall / (incident_precision + incident_recall)
        )
        incident_false_positive_rate = incident_false_positive / max(
            incident_false_positive + incident_true_negative,
            1,
        )
        if successful:
            factual_claim_count = sum(item.metrics.factual_claim_count for item in successful)
            supported_factual_claim_count = sum(
                item.metrics.supported_factual_claim_count for item in successful
            )
            unsupported_factual_claim_count = sum(
                item.metrics.unsupported_factual_claim_count for item in successful
            )
            contradictory_factual_claim_count = sum(
                item.metrics.contradictory_factual_claim_count for item in successful
            )
            if factual_claim_count == 0:
                factual_claim_support_rate = 0.0
                unsupported_factual_claim_rate = 0.0
                contradictory_factual_claim_rate = 0.0
            else:
                factual_claim_support_rate = supported_factual_claim_count / factual_claim_count
                unsupported_factual_claim_rate = (
                    unsupported_factual_claim_count / factual_claim_count
                )
                contradictory_factual_claim_rate = (
                    contradictory_factual_claim_count / factual_claim_count
                )
            summary = EvaluationSummary(
                mode=mode,
                runs=len(scoped),
                success_rate=round(len(successful) / len(scoped), 4),
                incident_precision=round(incident_precision, 4),
                incident_recall=round(incident_recall, 4),
                incident_f1=round(incident_f1, 4),
                incident_false_positive_rate=round(incident_false_positive_rate, 4),
                incident_count_correctness=round(
                    mean(item.metrics.incident_count_correctness for item in scoped),
                    4,
                ),
                incident_true_positive=incident_true_positive,
                incident_false_positive=incident_false_positive,
                incident_false_negative=incident_false_negative,
                incident_true_negative=incident_true_negative,
                root_cause_correctness=round(
                    mean(item.metrics.root_cause_correctness for item in successful), 4
                ),
                impacted_service_correctness=round(
                    mean(item.metrics.impacted_service_correctness for item in successful), 4
                ),
                impacted_service_precision=round(
                    mean(item.metrics.impacted_service_precision for item in successful), 4
                ),
                impacted_service_recall=round(
                    mean(item.metrics.impacted_service_recall for item in successful), 4
                ),
                impacted_service_f1=round(
                    mean(item.metrics.impacted_service_f1 for item in successful), 4
                ),
                anomaly_type_recall=round(
                    mean(item.metrics.anomaly_type_recall for item in successful), 4
                ),
                service_entity_precision=round(
                    mean(item.metrics.service_entity_precision for item in successful),
                    4,
                ),
                unexpected_service_mention_rate=round(
                    mean(item.metrics.unexpected_service_mention_rate for item in successful),
                    4,
                ),
                citation_coverage=round(
                    mean(item.metrics.citation_coverage for item in successful),
                    4,
                ),
                retrieval_relevance=round(
                    mean(item.metrics.retrieval_relevance for item in successful),
                    4,
                ),
                factual_claim_count=factual_claim_count,
                supported_factual_claim_count=supported_factual_claim_count,
                unsupported_factual_claim_count=unsupported_factual_claim_count,
                contradictory_factual_claim_count=contradictory_factual_claim_count,
                factual_claim_support_rate=round(factual_claim_support_rate, 4),
                unsupported_factual_claim_rate=round(unsupported_factual_claim_rate, 4),
                contradictory_factual_claim_rate=round(contradictory_factual_claim_rate, 4),
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
                incident_precision=round(incident_precision, 4),
                incident_recall=round(incident_recall, 4),
                incident_f1=round(incident_f1, 4),
                incident_false_positive_rate=round(incident_false_positive_rate, 4),
                incident_count_correctness=round(
                    mean(item.metrics.incident_count_correctness for item in scoped),
                    4,
                ),
                incident_true_positive=incident_true_positive,
                incident_false_positive=incident_false_positive,
                incident_false_negative=incident_false_negative,
                incident_true_negative=incident_true_negative,
                root_cause_correctness=0.0,
                impacted_service_correctness=0.0,
                impacted_service_precision=0.0,
                impacted_service_recall=0.0,
                impacted_service_f1=0.0,
                anomaly_type_recall=0.0,
                service_entity_precision=0.0,
                unexpected_service_mention_rate=1.0,
                citation_coverage=0.0,
                retrieval_relevance=0.0,
                factual_claim_count=0,
                supported_factual_claim_count=0,
                unsupported_factual_claim_count=0,
                contradictory_factual_claim_count=0,
                factual_claim_support_rate=0.0,
                unsupported_factual_claim_rate=0.0,
                contradictory_factual_claim_rate=0.0,
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
        "| Mode | Runs | Success | Incident F1 | False Positive Rate | Incident Count | "
        "Root Cause | Impacted F1 | Anomaly Recall | Service Precision | Unexpected Services | "
        "Claim Support | Unsupported Claims | Contradictory Claims | Citation Coverage | "
        "Retrieval Relevance | Completeness | Latency (s) | Avg Tokens | Total Cost (USD) |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    lines = []
    for summary in result.summaries:
        avg_tokens = (
            summary.average_token_usage if summary.average_token_usage is not None else "n/a"
        )
        total_cost = (
            summary.total_estimated_cost_usd
            if summary.total_estimated_cost_usd is not None
            else "n/a"
        )
        lines.append(
            "| "
            f"{summary.mode.value} | {summary.runs} | {summary.success_rate:.2f} | "
            f"{summary.incident_f1:.2f} | {summary.incident_false_positive_rate:.2f} | "
            f"{summary.incident_count_correctness:.2f} | "
            f"{summary.root_cause_correctness:.2f} | {summary.impacted_service_f1:.2f} | "
            f"{summary.anomaly_type_recall:.2f} | "
            f"{summary.service_entity_precision:.2f} | "
            f"{summary.unexpected_service_mention_rate:.2f} | "
            f"{summary.factual_claim_support_rate:.2f} | "
            f"{summary.unsupported_factual_claim_rate:.2f} | "
            f"{summary.contradictory_factual_claim_rate:.2f} | "
            f"{summary.citation_coverage:.2f} | {summary.retrieval_relevance:.2f} | "
            f"{summary.report_completeness:.2f} | {summary.latency_seconds:.2f} | "
            f"{avg_tokens} | {total_cost} |"
        )
    return header + "\n".join(lines) + "\n"


def compare_evaluation_summaries(
    *,
    baseline_summary_path: str,
    candidate_summary_path: str,
    thresholds: EvaluationRegressionThresholds | None = None,
) -> EvaluationComparisonResult:
    """Compare evaluation summary artifacts and detect quality regressions."""

    limit = thresholds or EvaluationRegressionThresholds()
    baseline = _load_summary_rows(baseline_summary_path)
    candidate = _load_summary_rows(candidate_summary_path)
    baseline_by_mode = {item.mode: item for item in baseline}
    candidate_by_mode = {item.mode: item for item in candidate}
    mode_order = {mode: index for index, mode in enumerate(evaluation_modes(include_real_llm=True))}

    findings: list[EvaluationComparisonFinding] = []
    for mode, baseline_summary in baseline_by_mode.items():
        if mode not in candidate_by_mode:
            findings.append(
                EvaluationComparisonFinding(
                    mode=mode,
                    metric="mode_missing",
                    baseline_value=1.0,
                    candidate_value=0.0,
                    delta=-1.0,
                    threshold=0.0,
                )
            )
            continue
        candidate_summary = candidate_by_mode[mode]
        findings.extend(
            _metric_regressions_for_mode(
                mode=mode,
                baseline=baseline_summary,
                candidate=candidate_summary,
                thresholds=limit,
            )
        )
    unexpected_modes = sorted(
        candidate_by_mode.keys() - baseline_by_mode.keys(),
        key=lambda mode: mode_order.get(mode, len(mode_order)),
    )
    for mode in unexpected_modes:
        findings.append(
            EvaluationComparisonFinding(
                mode=mode,
                metric="mode_unexpected",
                baseline_value=0.0,
                candidate_value=1.0,
                delta=1.0,
                threshold=0.0,
            )
        )

    return EvaluationComparisonResult(
        passed=not findings,
        baseline_summary_path=baseline_summary_path,
        candidate_summary_path=candidate_summary_path,
        findings=findings,
    )


def write_comparison_artifacts(
    *,
    output_dir: str,
    comparison: EvaluationComparisonResult,
) -> None:
    """Persist machine-readable and markdown comparison artifacts."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "eval_comparison.json").write_text(
        comparison.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (target / "eval_comparison.md").write_text(
        _comparison_markdown(comparison),
        encoding="utf-8",
    )


def _load_summary_rows(path: str) -> list[EvaluationSummary]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Evaluation summary must be a list: {path}")
    return [EvaluationSummary.model_validate(item) for item in payload]


def _metric_regressions_for_mode(
    *,
    mode: EvaluationMode,
    baseline: EvaluationSummary,
    candidate: EvaluationSummary,
    thresholds: EvaluationRegressionThresholds,
) -> list[EvaluationComparisonFinding]:
    findings: list[EvaluationComparisonFinding] = []
    checks = [
        (
            "success_rate",
            baseline.success_rate,
            candidate.success_rate,
            thresholds.success_rate_drop_max,
            "drop",
        ),
        (
            "incident_f1",
            baseline.incident_f1,
            candidate.incident_f1,
            thresholds.incident_f1_drop_max,
            "drop",
        ),
        (
            "incident_false_positive_rate",
            baseline.incident_false_positive_rate,
            candidate.incident_false_positive_rate,
            thresholds.incident_false_positive_rate_increase_max,
            "increase",
        ),
        (
            "incident_count_correctness",
            baseline.incident_count_correctness,
            candidate.incident_count_correctness,
            thresholds.incident_count_correctness_drop_max,
            "drop",
        ),
        (
            "root_cause_correctness",
            baseline.root_cause_correctness,
            candidate.root_cause_correctness,
            thresholds.root_cause_correctness_drop_max,
            "drop",
        ),
        (
            "impacted_service_correctness",
            baseline.impacted_service_correctness,
            candidate.impacted_service_correctness,
            thresholds.impacted_service_correctness_drop_max,
            "drop",
        ),
        (
            "impacted_service_f1",
            baseline.impacted_service_f1,
            candidate.impacted_service_f1,
            thresholds.impacted_service_f1_drop_max,
            "drop",
        ),
        (
            "anomaly_type_recall",
            baseline.anomaly_type_recall,
            candidate.anomaly_type_recall,
            thresholds.anomaly_type_recall_drop_max,
            "drop",
        ),
        (
            "service_entity_precision",
            baseline.service_entity_precision,
            candidate.service_entity_precision,
            thresholds.service_entity_precision_drop_max,
            "drop",
        ),
        (
            "unexpected_service_mention_rate",
            baseline.unexpected_service_mention_rate,
            candidate.unexpected_service_mention_rate,
            thresholds.unexpected_service_mention_rate_increase_max,
            "increase",
        ),
        (
            "citation_coverage",
            baseline.citation_coverage,
            candidate.citation_coverage,
            thresholds.citation_coverage_drop_max,
            "drop",
        ),
        (
            "report_completeness",
            baseline.report_completeness,
            candidate.report_completeness,
            thresholds.report_completeness_drop_max,
            "drop",
        ),
        (
            "factual_claim_support_rate",
            baseline.factual_claim_support_rate,
            candidate.factual_claim_support_rate,
            thresholds.factual_claim_support_rate_drop_max,
            "drop",
        ),
        (
            "unsupported_factual_claim_rate",
            baseline.unsupported_factual_claim_rate,
            candidate.unsupported_factual_claim_rate,
            thresholds.unsupported_factual_claim_rate_increase_max,
            "increase",
        ),
        (
            "contradictory_factual_claim_rate",
            baseline.contradictory_factual_claim_rate,
            candidate.contradictory_factual_claim_rate,
            thresholds.contradictory_factual_claim_rate_increase_max,
            "increase",
        ),
    ]

    for metric, base_value, candidate_value, threshold, kind in checks:
        delta = round(candidate_value - base_value, 4)
        if kind == "drop" and delta < -threshold:
            findings.append(
                EvaluationComparisonFinding(
                    mode=mode,
                    metric=metric,
                    baseline_value=base_value,
                    candidate_value=candidate_value,
                    delta=delta,
                    threshold=threshold,
                )
            )
        if kind == "increase" and delta > threshold:
            findings.append(
                EvaluationComparisonFinding(
                    mode=mode,
                    metric=metric,
                    baseline_value=base_value,
                    candidate_value=candidate_value,
                    delta=delta,
                    threshold=threshold,
                )
            )
    return findings


def _comparison_markdown(comparison: EvaluationComparisonResult) -> str:
    header = (
        "# Evaluation Regression Comparison\n\n"
        f"Passed: `{comparison.passed}`\n\n"
        f"- Baseline: `{comparison.baseline_summary_path}`\n"
        f"- Candidate: `{comparison.candidate_summary_path}`\n\n"
    )
    if not comparison.findings:
        return header + "No regressions detected.\n"

    table_header = (
        "| Mode | Metric | Baseline | Candidate | Delta | Threshold |\n"
        "|---|---|---:|---:|---:|---:|\n"
    )
    rows = [
        (
            f"| {item.mode.value} | {item.metric} | {item.baseline_value:.4f} | "
            f"{item.candidate_value:.4f} | {item.delta:.4f} | {item.threshold:.4f} |"
        )
        for item in comparison.findings
    ]
    return header + table_header + "\n".join(rows) + "\n"
