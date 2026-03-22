"""End-to-end incident analysis pipeline orchestration."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from incident_agent.anomaly_detection.engine import (
    detect_anomalies,
    load_anomaly_detection_config,
)
from incident_agent.core.settings import load_observability_config
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
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.schemas.llm import LLMCompletionRequest
from incident_agent.schemas.pipeline import PipelineRunResult
from incident_agent.schemas.rca import RCAResult
from incident_agent.utils.observability import (
    bind_context,
    configure_logging,
    execution_span,
    get_logger,
    log_event,
)

logger = get_logger(__name__)


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
    configure_logging(level=observability.log_level, json_logs=observability.json_logs)

    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    run_dir = Path(artifact_root) / run_id

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
                logs = load_logs(log_path)
                metrics = load_metrics(metric_path)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="ingestion counts",
                    stage="ingest",
                    log_count=len(logs),
                    metric_count=len(metrics),
                )

            with execution_span(logger, event_prefix="pipeline.stage", stage="normalize"):
                normalization_config = load_normalization_config(config_path)
                if bucket_size_minutes is not None:
                    normalization_config = NormalizationConfig(
                        **{
                            **normalization_config.model_dump(),
                            "bucket_size_minutes": bucket_size_minutes,
                        }
                    )
                alignment = align_events_to_timeline(logs, metrics, config=normalization_config)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="normalization counts",
                    stage="normalize",
                    event_count=len(alignment.events),
                    bucket_count=len(alignment.buckets),
                )

            with execution_span(logger, event_prefix="pipeline.stage", stage="anomaly_detection"):
                anomaly_config = load_anomaly_detection_config(config_path)
                anomalies = detect_anomalies(
                    alignment,
                    bucket_size_minutes=normalization_config.bucket_size_minutes,
                    config=anomaly_config,
                )
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="anomaly counts",
                    stage="anomaly_detection",
                    anomaly_count=len(anomalies.anomalies),
                )

            with execution_span(logger, event_prefix="pipeline.stage", stage="correlation"):
                correlation_config = load_correlation_config(config_path)
                correlation_graph = load_dependency_graph_for_correlation(correlation_config)
                incidents = correlate_anomalies(
                    anomalies.anomalies,
                    config=correlation_config,
                    dependency_graph=correlation_graph,
                )
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="incident counts",
                    stage="correlation",
                    incident_count=len(incidents.incidents),
                )

            with execution_span(logger, event_prefix="pipeline.stage", stage="rca"):
                rca_config = load_rca_config(config_path)
                rca_graph = load_dependency_graph_for_rca(rca_config)
                rca_result = perform_rca(
                    incidents.incidents,
                    config=rca_config,
                    dependency_graph=rca_graph,
                )
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="rca counts",
                    stage="rca",
                    hypothesis_count=len(rca_result.hypotheses),
                )

            with execution_span(logger, event_prefix="pipeline.stage", stage="report_generation"):
                llm_config = load_llm_config(config_path)
                provider = create_provider(llm_config)
                reports = _generate_final_reports(
                    rca_result,
                    provider=provider,
                    completion_model=llm_config.completion_model,
                )
                log_event(
                    logger,
                    level=logging.INFO,
                    event="pipeline.stage.counts",
                    message="report counts",
                    stage="report_generation",
                    report_count=len(reports),
                )

            with execution_span(logger, event_prefix="pipeline.stage", stage="persist_artifacts"):
                _persist_artifacts(
                    run_dir=run_dir,
                    alignment=alignment.model_dump(mode="json"),
                    anomalies=anomalies.model_dump(mode="json"),
                    incidents=incidents.model_dump(mode="json"),
                    rca=rca_result.model_dump(mode="json"),
                    reports=[report.model_dump(mode="json") for report in reports],
                )

            result = PipelineRunResult(
                run_id=run_id,
                artifact_dir=str(run_dir),
                normalized_event_count=len(alignment.events),
                anomaly_count=len(anomalies.anomalies),
                incident_count=len(incidents.incidents),
                hypothesis_count=len(rca_result.hypotheses),
                final_report_count=len(reports),
                final_reports=reports,
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
            line.strip("- ").strip()
            for line in remediation_text.splitlines()
            if line.strip()
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


def _persist_artifacts(
    *,
    run_dir: Path,
    alignment: dict[str, object],
    anomalies: dict[str, object],
    incidents: dict[str, object],
    rca: dict[str, object],
    reports: list[dict[str, object]],
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
