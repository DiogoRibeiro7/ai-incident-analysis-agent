"""End-to-end incident analysis pipeline orchestration."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar, cast
from uuid import uuid4

from incident_agent.anomaly_detection.engine import (
    detect_anomalies,
    load_anomaly_detection_config,
)
from incident_agent.core.settings import load_observability_config, load_resilience_config
from incident_agent.correlation.engine import (
    correlate_anomalies,
    load_correlation_config,
    load_dependency_graph_for_correlation,
)
from incident_agent.ingest.files import load_logs, load_metrics
from incident_agent.llm.base import BaseLLMProvider, LLMProviderError
from incident_agent.llm.factory import create_provider, load_llm_config
from incident_agent.normalization.timeline import (
    NormalizationConfig,
    align_events_to_timeline,
    load_normalization_config,
)
from incident_agent.prompts.renderer import PromptRenderContext, render_all_prompts
from incident_agent.rca.engine import (
    load_dependency_graph_for_rca,
    load_rca_config,
    perform_rca,
)
from incident_agent.schemas.anomaly import AnomalyDetectionResult
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.schemas.incident import IncidentCorrelationResult
from incident_agent.schemas.llm import LLMCompletionRequest
from incident_agent.schemas.pipeline import PipelineFailureSummary, PipelineRunResult
from incident_agent.schemas.rca import RCAResult
from incident_agent.schemas.timeline import TimelineAlignmentResult
from incident_agent.utils.observability import (
    bind_context,
    configure_logging,
    execution_span,
    get_logger,
    log_event,
)
from incident_agent.utils.resilience import JsonFileCache, file_fingerprint, stable_cache_key

logger = get_logger(__name__)
ModelT = TypeVar("ModelT")


def run_pipeline_from_files(
    *,
    log_path: str,
    metric_path: str,
    config_path: str = "configs/default.yaml",
    artifact_root: str = "artifacts/pipeline",
    bucket_size_minutes: int | None = None,
) -> PipelineRunResult:
    """Run ingestion, normalization, anomaly detection, correlation, RCA, and reporting."""
    observability = load_observability_config(config_path)
    resilience = load_resilience_config(config_path)
    configure_logging(level=observability.log_level, json_logs=observability.json_logs)

    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    run_dir = Path(artifact_root) / run_id
    stage_cache = (
        JsonFileCache(resilience.intermediate_cache_dir)
        if resilience.enable_intermediate_cache
        else None
    )
    warnings: list[str] = []
    failure_summaries: list[PipelineFailureSummary] = []
    completed_stages: list[str] = []
    used_intermediate_cache = False

    with bind_context(run_id=run_id):
        log_event(
            logger,
            level=logging.INFO,
            event="pipeline.run.started",
            message="pipeline run started",
            log_path=log_path,
            metric_path=metric_path,
            config_path=config_path,
            artifact_root=artifact_root,
            bucket_size_minutes=bucket_size_minutes,
        )
        try:
            with execution_span(logger, event_prefix="pipeline.stage", stage="ingest"):
                logs = _load_logs_with_degradation(
                    path=log_path,
                    allow_missing=resilience.allow_missing_logs,
                    warnings=warnings,
                    failure_summaries=failure_summaries,
                )
                metrics = _load_metrics_with_degradation(
                    path=metric_path,
                    allow_missing=resilience.allow_missing_metrics,
                    warnings=warnings,
                    failure_summaries=failure_summaries,
                )
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="ingestion counts",
                    stage="ingest",
                    log_count=len(logs),
                    metric_count=len(metrics),
                )
            completed_stages.append("ingest")

            if not logs and not metrics:
                failure_summaries.append(
                    PipelineFailureSummary(
                        stage="ingest",
                        message="No usable logs or metrics were available for analysis.",
                        fatal=False,
                    )
                )
                result = _build_pipeline_result(
                    run_id=run_id,
                    run_dir=run_dir,
                    alignment=TimelineAlignmentResult(),
                    anomalies=AnomalyDetectionResult(),
                    incidents=IncidentCorrelationResult(),
                    rca_result=RCAResult(),
                    reports=[],
                    warnings=warnings,
                    failure_summaries=failure_summaries,
                    completed_stages=completed_stages,
                    used_intermediate_cache=used_intermediate_cache,
                    used_llm_cache=False,
                )
                alignment_payload, anomalies_payload, incidents_payload, rca_payload = (
                    _artifact_payloads(
                        alignment=TimelineAlignmentResult(),
                        anomalies=AnomalyDetectionResult(),
                        incidents=IncidentCorrelationResult(),
                        rca_result=RCAResult(),
                    )
                )
                _persist_artifacts(
                    run_dir=run_dir,
                    alignment=alignment_payload,
                    anomalies=anomalies_payload,
                    incidents=incidents_payload,
                    rca=rca_payload,
                    reports=[report.model_dump(mode="json") for report in result.final_reports],
                    run_summary=_run_summary_payload(result),
                )
                return result

            with execution_span(logger, event_prefix="pipeline.stage", stage="normalize"):
                normalization_config = load_normalization_config(config_path)
                if bucket_size_minutes is not None:
                    normalization_config = NormalizationConfig(
                        **{
                            **normalization_config.model_dump(),
                            "bucket_size_minutes": bucket_size_minutes,
                        }
                    )
                normalize_cache_key = stable_cache_key(
                    "normalize",
                    config_path,
                    normalization_config.model_dump(mode="json"),
                    file_fingerprint(log_path),
                    file_fingerprint(metric_path),
                )
                alignment, cache_hit = _load_or_compute_stage(
                    cache=stage_cache,
                    cache_key=normalize_cache_key,
                    model_type=TimelineAlignmentResult,
                    compute=lambda: align_events_to_timeline(
                        logs,
                        metrics,
                        config=normalization_config,
                    ),
                )
                used_intermediate_cache = used_intermediate_cache or cache_hit
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="normalization counts",
                    stage="normalize",
                    event_count=len(alignment.events),
                    bucket_count=len(alignment.buckets),
                )
            completed_stages.append("normalize")

            with execution_span(logger, event_prefix="pipeline.stage", stage="anomaly_detection"):
                anomaly_config = load_anomaly_detection_config(config_path)
                anomaly_cache_key = stable_cache_key(
                    "anomaly_detection",
                    normalize_cache_key,
                    anomaly_config.model_dump(mode="json"),
                )
                anomalies, cache_hit = _load_or_compute_stage(
                    cache=stage_cache,
                    cache_key=anomaly_cache_key,
                    model_type=AnomalyDetectionResult,
                    compute=lambda: detect_anomalies(
                        alignment,
                        bucket_size_minutes=normalization_config.bucket_size_minutes,
                        config=anomaly_config,
                    ),
                )
                used_intermediate_cache = used_intermediate_cache or cache_hit
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="anomaly counts",
                    stage="anomaly_detection",
                    anomaly_count=len(anomalies.anomalies),
                )
            completed_stages.append("anomaly_detection")

            with execution_span(logger, event_prefix="pipeline.stage", stage="correlation"):
                correlation_config = load_correlation_config(config_path)
                correlation_graph = load_dependency_graph_for_correlation(correlation_config)
                correlation_cache_key = stable_cache_key(
                    "correlation",
                    anomaly_cache_key,
                    correlation_config.model_dump(mode="json"),
                )
                incidents, cache_hit = _load_or_compute_stage(
                    cache=stage_cache,
                    cache_key=correlation_cache_key,
                    model_type=IncidentCorrelationResult,
                    compute=lambda: correlate_anomalies(
                        anomalies.anomalies,
                        config=correlation_config,
                        dependency_graph=correlation_graph,
                    ),
                )
                used_intermediate_cache = used_intermediate_cache or cache_hit
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="incident counts",
                    stage="correlation",
                    incident_count=len(incidents.incidents),
                )
            completed_stages.append("correlation")

            with execution_span(logger, event_prefix="pipeline.stage", stage="rca"):
                rca_config = load_rca_config(config_path)
                rca_graph = load_dependency_graph_for_rca(rca_config)
                rca_cache_key = stable_cache_key(
                    "rca",
                    correlation_cache_key,
                    rca_config.model_dump(mode="json"),
                )
                rca_result, cache_hit = _load_or_compute_stage(
                    cache=stage_cache,
                    cache_key=rca_cache_key,
                    model_type=RCAResult,
                    compute=lambda: perform_rca(
                        incidents.incidents,
                        config=rca_config,
                        dependency_graph=rca_graph,
                    ),
                )
                used_intermediate_cache = used_intermediate_cache or cache_hit
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="rca counts",
                    stage="rca",
                    hypothesis_count=len(rca_result.hypotheses),
                )
            completed_stages.append("rca")

            used_llm_cache = resilience.enable_llm_cache
            with execution_span(logger, event_prefix="pipeline.stage", stage="report_generation"):
                reports: list[FinalIncidentReport] = []
                try:
                    llm_config = load_llm_config(config_path)
                    provider = create_provider(llm_config, config_path=config_path)
                    reports = _generate_final_reports(
                        rca_result,
                        provider=provider,
                        completion_model=llm_config.completion_model,
                    )
                except Exception as error:
                    failure_summaries.append(
                        PipelineFailureSummary(
                            stage="report_generation",
                            message=f"Report generation degraded: {error}",
                            fatal=False,
                        )
                    )
                    warnings.append(
                        "Final report generation failed; upstream artifacts were preserved."
                    )
                    reports = []
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="report counts",
                    stage="report_generation",
                    report_count=len(reports),
                )
            completed_stages.append("report_generation")

            with execution_span(logger, event_prefix="pipeline.stage", stage="persist_artifacts"):
                completed_stages.append("persist_artifacts")
                result = _build_pipeline_result(
                    run_id=run_id,
                    run_dir=run_dir,
                    alignment=alignment,
                    anomalies=anomalies,
                    incidents=incidents,
                    rca_result=rca_result,
                    reports=reports,
                    warnings=warnings,
                    failure_summaries=failure_summaries,
                    completed_stages=completed_stages,
                    used_intermediate_cache=used_intermediate_cache,
                    used_llm_cache=used_llm_cache,
                )
                alignment_payload, anomalies_payload, incidents_payload, rca_payload = (
                    _artifact_payloads(
                        alignment=alignment,
                        anomalies=anomalies,
                        incidents=incidents,
                        rca_result=rca_result,
                    )
                )
                _persist_artifacts(
                    run_dir=run_dir,
                    alignment=alignment_payload,
                    anomalies=anomalies_payload,
                    incidents=incidents_payload,
                    rca=rca_payload,
                    reports=[report.model_dump(mode="json") for report in reports],
                    run_summary=_run_summary_payload(result),
                )

            log_event(
                logger,
                level=logging.INFO,
                event="pipeline.run.completed",
                message="pipeline run completed",
                normalized_event_count=result.normalized_event_count,
                anomaly_count=result.anomaly_count,
                incident_count=result.incident_count,
                hypothesis_count=result.hypothesis_count,
                final_report_count=result.final_report_count,
                artifact_dir=result.artifact_dir,
                degraded=result.degraded,
            )
            return result
        except Exception as error:
            log_event(
                logger,
                level=logging.ERROR,
                event="pipeline.run.failed",
                message="pipeline run failed",
                error_type=type(error).__name__,
                error=str(error),
            )
            raise


def _generate_final_reports(
    rca_result: RCAResult,
    *,
    provider: BaseLLMProvider,
    completion_model: str,
) -> list[FinalIncidentReport]:
    reports: list[FinalIncidentReport] = []
    bundle_by_id = {bundle.incident_id: bundle for bundle in rca_result.bundles}
    summary_by_id = {summary.incident_id: summary for summary in rca_result.summaries}

    for hypothesis in rca_result.hypotheses:
        bundle = bundle_by_id[hypothesis.incident_id]
        summary = summary_by_id[hypothesis.incident_id]
        context = PromptRenderContext(
            incident_id=hypothesis.incident_id,
            evidence_bundle=bundle,
            summary_features=summary,
            root_cause_hypothesis=hypothesis,
        )
        prompts = render_all_prompts(context)

        incident_summary = _complete_or_fallback(
            provider=provider,
            model=completion_model,
            prompt=prompts["incident_summary"],
            fallback=(
                f"Incident {hypothesis.incident_id} impacted services: "
                f"{', '.join(summary.impacted_services)}."
            ),
        )
        root_cause_explanation = _complete_or_fallback(
            provider=provider,
            model=completion_model,
            prompt=prompts["root_cause_explanation"],
            fallback=(
                f"Most likely root cause is {hypothesis.suspected_root_cause_service} "
                f"with confidence {hypothesis.confidence_score:.2f}."
            ),
        )
        executive_summary = _complete_or_fallback(
            provider=provider,
            model=completion_model,
            prompt=prompts["executive_summary"],
            fallback="Service degradation detected and triaged with heuristic RCA output.",
        )
        engineering_handoff = _complete_or_fallback(
            provider=provider,
            model=completion_model,
            prompt=prompts["engineering_handoff"],
            fallback=(
                "Inspect root service dependency timeouts, saturation metrics, and recent changes."
            ),
        )
        remediation_text = _complete_or_fallback(
            provider=provider,
            model=completion_model,
            prompt=prompts["remediation_suggestions"],
            fallback=(
                "Contain incident by rollback or traffic shaping, then harden alerts and "
                "dependency protections."
            ),
        )

        facts = [
            (
                f"{item.affected_service}: {item.anomaly_type} observed={item.observed_value} "
                f"baseline={item.baseline_value}"
            )
            for item in bundle.ranked_evidence[:5]
        ]
        inferences = [hypothesis.rationale]
        uncertainties = hypothesis.unresolved_ambiguities
        remediation_suggestions = [
            line.strip("- ").strip() for line in remediation_text.splitlines() if line.strip()
        ][:5]
        if not remediation_suggestions:
            remediation_suggestions = [remediation_text]

        reports.append(
            FinalIncidentReport(
                incident_id=hypothesis.incident_id,
                incident_summary=incident_summary,
                root_cause_explanation=root_cause_explanation,
                executive_summary=executive_summary,
                engineering_handoff=engineering_handoff,
                remediation_suggestions=remediation_suggestions,
                facts=facts,
                inferences=inferences,
                uncertainties=uncertainties,
            )
        )
    return reports


def _complete_or_fallback(
    *,
    provider: BaseLLMProvider,
    model: str,
    prompt: str,
    fallback: str,
) -> str:
    try:
        response = provider.complete(
            LLMCompletionRequest(
                prompt=prompt,
                model=model,
            )
        )
        return response.content.strip() or fallback
    except LLMProviderError:
        return fallback


def _load_logs_with_degradation(
    *,
    path: str,
    allow_missing: bool,
    warnings: list[str],
    failure_summaries: list[PipelineFailureSummary],
) -> list[LogEvent]:
    return cast(
        list[LogEvent],
        _load_records_with_degradation(
            path=path,
            dataset_name="logs",
            allow_missing=allow_missing,
            warnings=warnings,
            failure_summaries=failure_summaries,
        ),
    )


def _load_metrics_with_degradation(
    *,
    path: str,
    allow_missing: bool,
    warnings: list[str],
    failure_summaries: list[PipelineFailureSummary],
) -> list[MetricPoint]:
    return cast(
        list[MetricPoint],
        _load_records_with_degradation(
            path=path,
            dataset_name="metrics",
            allow_missing=allow_missing,
            warnings=warnings,
            failure_summaries=failure_summaries,
        ),
    )


def _load_records_with_degradation(
    *,
    path: str,
    dataset_name: str,
    allow_missing: bool,
    warnings: list[str],
    failure_summaries: list[PipelineFailureSummary],
) -> list[LogEvent] | list[MetricPoint]:
    loader = load_logs if dataset_name == "logs" else load_metrics
    try:
        return loader(path)
    except FileNotFoundError:
        if not allow_missing:
            raise
        message = f"{dataset_name} input missing at {path}; continuing with available data."
    except ValueError as error:
        if not allow_missing:
            raise
        message = (
            f"{dataset_name} input invalid at {path}: {error}; continuing with available data."
        )
    else:
        return []

    warnings.append(message)
    failure_summaries.append(PipelineFailureSummary(stage="ingest", message=message, fatal=False))
    log_event(
        logger,
        level=logging.WARNING,
        event="pipeline.ingest.degraded",
        message=message,
        dataset=dataset_name,
        path=path,
    )
    return []


def _load_or_compute_stage(
    *,
    cache: JsonFileCache | None,
    cache_key: str,
    model_type: type[ModelT],
    compute: Callable[[], ModelT],
) -> tuple[ModelT, bool]:
    if cache is not None:
        cached = cache.read(cache_key)
        if cached is not None:
            log_event(
                logger,
                level=logging.INFO,
                event="pipeline.cache.hit",
                message="loaded intermediate artifact from cache",
                cache_key=cache_key,
            )
            return model_type.model_validate(cached), True  # type: ignore[attr-defined]

    result = compute()
    if cache is not None:
        cache.write(cache_key, result.model_dump(mode="json"))  # type: ignore[attr-defined]
        log_event(
            logger,
            level=logging.INFO,
            event="pipeline.cache.store",
            message="stored intermediate artifact in cache",
            cache_key=cache_key,
        )
    return result, False


def _build_pipeline_result(
    *,
    run_id: str,
    run_dir: Path,
    alignment: TimelineAlignmentResult,
    anomalies: AnomalyDetectionResult,
    incidents: IncidentCorrelationResult,
    rca_result: RCAResult,
    reports: list[FinalIncidentReport],
    warnings: list[str],
    failure_summaries: list[PipelineFailureSummary],
    completed_stages: list[str],
    used_intermediate_cache: bool,
    used_llm_cache: bool,
) -> PipelineRunResult:
    return PipelineRunResult(
        run_id=run_id,
        artifact_dir=str(run_dir),
        normalized_event_count=len(alignment.events),
        anomaly_count=len(anomalies.anomalies),
        incident_count=len(incidents.incidents),
        hypothesis_count=len(rca_result.hypotheses),
        final_report_count=len(reports),
        degraded=bool(warnings or failure_summaries),
        completed_stages=completed_stages.copy(),
        warnings=warnings.copy(),
        failure_summaries=failure_summaries.copy(),
        used_intermediate_cache=used_intermediate_cache,
        used_llm_cache=used_llm_cache,
        final_reports=reports,
    )


def _artifact_payloads(
    *,
    alignment: TimelineAlignmentResult,
    anomalies: AnomalyDetectionResult,
    incidents: IncidentCorrelationResult,
    rca_result: RCAResult,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    return (
        alignment.model_dump(mode="json"),
        anomalies.model_dump(mode="json"),
        incidents.model_dump(mode="json"),
        rca_result.model_dump(mode="json"),
    )


def _run_summary_payload(result: PipelineRunResult) -> dict[str, object]:
    return result.model_dump(mode="json")


def _persist_artifacts(
    *,
    run_dir: Path,
    alignment: dict[str, object],
    anomalies: dict[str, object],
    incidents: dict[str, object],
    rca: dict[str, object],
    reports: list[dict[str, object]],
    run_summary: dict[str, object],
) -> None:
    normalized_dir = run_dir / "normalized"
    anomalies_dir = run_dir / "anomalies"
    incidents_dir = run_dir / "incidents"
    rca_dir = run_dir / "rca"
    reports_dir = run_dir / "reports"
    for directory in [normalized_dir, anomalies_dir, incidents_dir, rca_dir, reports_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    (normalized_dir / "timeline.json").write_text(json.dumps(alignment, indent=2), encoding="utf-8")
    (anomalies_dir / "anomalies.json").write_text(json.dumps(anomalies, indent=2), encoding="utf-8")
    (incidents_dir / "incidents.json").write_text(json.dumps(incidents, indent=2), encoding="utf-8")
    (rca_dir / "rca_hypotheses.json").write_text(json.dumps(rca, indent=2), encoding="utf-8")
    (reports_dir / "final_reports.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    (run_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
