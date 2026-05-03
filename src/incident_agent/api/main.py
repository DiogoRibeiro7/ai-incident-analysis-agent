"""FastAPI application entrypoint for analysis workflows."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from incident_agent import __version__
from incident_agent.agents.incident_agent import IncidentAnalysisAgent
from incident_agent.api.store import AnalysisJobRecord, AnalysisJobStore
from incident_agent.core.settings import (
    load_observability_config,
    load_settings_from_yaml,
    load_webhook_export_config,
)
from incident_agent.export.webhook import (
    WebhookExportConfig,
    WebhookExportError,
    export_report_via_webhook,
)
from incident_agent.llm.factory import create_provider, load_llm_config
from incident_agent.schemas.anomaly import AnomalyCandidate
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.final_report import FinalIncidentReport, ReviewStatus
from incident_agent.schemas.incident import CorrelatedIncidentCandidate
from incident_agent.schemas.pipeline import PipelineRunResult
from incident_agent.schemas.report import IncidentReport
from incident_agent.services.pipeline import run_pipeline_from_files
from incident_agent.utils.observability import (
    bind_context,
    configure_logging,
    get_logger,
    log_event,
)

app = FastAPI(
    title="AI Incident Analysis Agent",
    version=__version__,
    description="Local incident analysis service with file-based workflow execution.",
)
app.state.job_store = AnalysisJobStore()
logger = get_logger(__name__)


def _setup_observability() -> None:
    try:
        config = load_observability_config()
        configure_logging(level=config.log_level, json_logs=config.json_logs)
    except Exception as error:
        configure_logging()
        log_event(
            logger,
            level=logging.WARNING,
            event="observability.config.fallback",
            message="failed to load observability config; using defaults",
            error_type=type(error).__name__,
            error=str(error),
        )


_setup_observability()


class ErrorResponse(BaseModel):
    """Standard API error payload."""

    detail: str


class AnalyzeRequest(BaseModel):
    """Request schema for ad hoc incident analysis."""

    logs: list[LogEvent]
    metrics: list[MetricPoint]


class AnalyzeResponse(BaseModel):
    """Response schema for ad hoc incident analysis."""

    reports: list[IncidentReport]


class PipelineAnalyzeRequest(BaseModel):
    """Request schema for full file-based pipeline execution."""

    logs_path: str
    metrics_path: str
    config_path: str = "configs/default.yaml"
    artifact_root: str = "artifacts/pipeline"
    bucket_size_minutes: int | None = None
    retrieval_enabled: bool | None = None
    knowledge_source_paths: list[str] | None = None
    metrics_source: str = "file"
    prometheus_url: str | None = None
    prometheus_step_seconds: int | None = None
    prometheus_queries: dict[str, str] | None = None


class ConfigInspectionResponse(BaseModel):
    """Config inspection response."""

    config_path: str
    config: dict[str, Any]


class AnalysisJobSubmitRequest(BaseModel):
    """Job submission request for local file-based execution."""

    logs_path: str
    metrics_path: str
    config_path: str = "configs/default.yaml"
    artifact_root: str = "artifacts/pipeline"
    bucket_size_minutes: int | None = None
    retrieval_enabled: bool | None = None
    knowledge_source_paths: list[str] | None = None
    metrics_source: str = "file"
    prometheus_url: str | None = None
    prometheus_step_seconds: int | None = None
    prometheus_queries: dict[str, str] | None = None


class AnalysisJobStatusResponse(BaseModel):
    """Job status response."""

    job_id: str
    status: str
    created_at: str
    updated_at: str
    run_id: str | None = None
    artifact_dir: str | None = None
    error: str | None = None


class AnalysisJobReportsResponse(BaseModel):
    """Report retrieval response for a job."""

    job_id: str
    reports: list[FinalIncidentReport] = Field(default_factory=list)


class ReportReviewTransitionRequest(BaseModel):
    """Request payload for report review transitions."""

    to_status: ReviewStatus
    reviewer: str = Field(min_length=1)
    note: str = Field(min_length=1)


class ReportReviewTransitionResponse(BaseModel):
    """Response payload after report review transition."""

    job_id: str
    report: FinalIncidentReport


class IncidentListResponse(BaseModel):
    """Incident listing response."""

    incidents: list[CorrelatedIncidentCandidate] = Field(default_factory=list)


class AnomalyListResponse(BaseModel):
    """Anomaly listing response."""

    anomalies: list[AnomalyCandidate] = Field(default_factory=list)


class ReportWebhookExportRequest(BaseModel):
    """Webhook export request payload."""

    destination_url: str
    config_path: str = "configs/default.yaml"


class ReportWebhookExportResponse(BaseModel):
    """Webhook export response payload."""

    job_id: str
    incident_id: str
    delivery_id: str
    status: str
    attempts: int
    payload_id: str | None = None


def get_job_store(request: Request) -> AnalysisJobStore:
    """Dependency injection provider for job store."""

    store = request.app.state.job_store
    if not isinstance(store, AnalysisJobStore):
        raise RuntimeError("Application job store is not initialized.")
    return store


@app.middleware("http")
async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or uuid4().hex
    start = perf_counter()
    with bind_context(request_id=request_id):
        log_event(
            logger,
            level=logging.INFO,
            event="api.request.started",
            message="api request started",
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception as error:
            duration_ms = round((perf_counter() - start) * 1000, 2)
            log_event(
                logger,
                level=logging.ERROR,
                event="api.request.failed",
                message="api request failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error_type=type(error).__name__,
                error=str(error),
            )
            raise
        duration_ms = round((perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        log_event(
            logger,
            level=logging.INFO,
            event="api.request.completed",
            message="api request completed",
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
            status_code=response.status_code,
        )
        return response


@app.get("/health", summary="Health check")
def health() -> dict[str, str]:
    """Simple health endpoint."""

    return {"status": "ok"}


@app.get(
    "/config",
    response_model=ConfigInspectionResponse,
    summary="Inspect loaded config",
    responses={400: {"model": ErrorResponse}},
)
def inspect_config(
    config_path: Annotated[
        str, Query(description="Path to YAML config file.")
    ] = "configs/default.yaml",
) -> ConfigInspectionResponse:
    """Inspect the YAML config used by local workflows."""

    path = Path(config_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Config path does not exist: {config_path}")
    loaded = load_settings_from_yaml(path)
    return ConfigInspectionResponse(config_path=config_path, config=loaded)


@app.post("/analyze", response_model=AnalyzeResponse, summary="Analyze ad hoc events")
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a batch of logs and metrics."""

    config = load_llm_config()
    provider = create_provider(config, config_path="configs/default.yaml")
    agent = IncidentAnalysisAgent(provider=provider, report_model=config.report_model)
    reports = agent.analyze(logs=request.logs, metrics=request.metrics)
    return AnalyzeResponse(reports=reports)


@app.post(
    "/analyze-pipeline",
    response_model=PipelineRunResult,
    summary="Run full local pipeline directly",
    responses={400: {"model": ErrorResponse}},
)
def analyze_pipeline(request: PipelineAnalyzeRequest) -> PipelineRunResult:
    """Run full file-based pipeline and persist output artifacts."""

    try:
        return run_pipeline_from_files(
            log_path=request.logs_path,
            metric_path=request.metrics_path,
            config_path=request.config_path,
            artifact_root=request.artifact_root,
            bucket_size_minutes=request.bucket_size_minutes,
            retrieval_enabled=request.retrieval_enabled,
            knowledge_source_paths=request.knowledge_source_paths,
            metrics_source=request.metrics_source,
            prometheus_url=request.prometheus_url,
            prometheus_step_seconds=request.prometheus_step_seconds,
            prometheus_queries=request.prometheus_queries,
        )
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Pipeline execution failed: {error}",
        ) from error


@app.post(
    "/analysis-jobs",
    response_model=AnalysisJobStatusResponse,
    summary="Submit local incident analysis job",
    responses={400: {"model": ErrorResponse}},
)
def submit_analysis_job(
    request: AnalysisJobSubmitRequest,
    job_store: Annotated[AnalysisJobStore, Depends(get_job_store)],
) -> AnalysisJobStatusResponse:
    """Submit and execute a local file-based analysis job."""

    job = job_store.create_submitted_job()
    try:
        pipeline_result = run_pipeline_from_files(
            log_path=request.logs_path,
            metric_path=request.metrics_path,
            config_path=request.config_path,
            artifact_root=request.artifact_root,
            bucket_size_minutes=request.bucket_size_minutes,
            retrieval_enabled=request.retrieval_enabled,
            knowledge_source_paths=request.knowledge_source_paths,
            metrics_source=request.metrics_source,
            prometheus_url=request.prometheus_url,
            prometheus_step_seconds=request.prometheus_step_seconds,
            prometheus_queries=request.prometheus_queries,
        )
        incidents = _load_incidents(pipeline_result.artifact_dir)
        anomalies = _load_anomalies(pipeline_result.artifact_dir)
        completed = job_store.mark_completed(
            job_id=job.job_id,
            run_id=pipeline_result.run_id,
            artifact_dir=pipeline_result.artifact_dir,
            reports=pipeline_result.final_reports,
            incidents=incidents,
            anomalies=anomalies,
        )
        return _status_response(completed)
    except Exception as error:
        failed = job_store.mark_failed(job_id=job.job_id, error=str(error))
        raise HTTPException(
            status_code=400,
            detail=f"Job {failed.job_id} failed: {error}",
        ) from error


@app.get(
    "/analysis-jobs/{job_id}/reports",
    response_model=AnalysisJobReportsResponse,
    summary="Retrieve final reports for a submitted job",
    responses={404: {"model": ErrorResponse}},
)
def get_job_reports(
    job_id: str,
    job_store: Annotated[AnalysisJobStore, Depends(get_job_store)],
) -> AnalysisJobReportsResponse:
    """Retrieve generated final reports for a job."""

    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return AnalysisJobReportsResponse(job_id=job_id, reports=job.reports)


@app.post(
    "/analysis-jobs/{job_id}/reports/{incident_id}/review",
    response_model=ReportReviewTransitionResponse,
    summary="Transition review status for one report",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def transition_job_report_review(
    job_id: str,
    incident_id: str,
    request: ReportReviewTransitionRequest,
    job_store: Annotated[AnalysisJobStore, Depends(get_job_store)],
) -> ReportReviewTransitionResponse:
    """Transition report lifecycle status and persist review metadata."""

    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    try:
        report = job_store.transition_report_review(
            job_id=job_id,
            incident_id=incident_id,
            to_status=request.to_status,
            reviewer=request.reviewer,
            note=request.note,
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Report not found for incident_id={incident_id}",
        ) from None
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ReportReviewTransitionResponse(job_id=job_id, report=report)


@app.post(
    "/analysis-jobs/{job_id}/reports/{incident_id}/export-webhook",
    response_model=ReportWebhookExportResponse,
    summary="Export approved report to generic webhook",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def export_job_report_webhook(
    job_id: str,
    incident_id: str,
    request: ReportWebhookExportRequest,
    job_store: Annotated[AnalysisJobStore, Depends(get_job_store)],
) -> ReportWebhookExportResponse:
    """Export one approved report and persist webhook delivery audit."""

    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    report = next((item for item in job.reports if item.incident_id == incident_id), None)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report not found for incident_id={incident_id}",
        )
    try:
        settings = load_webhook_export_config(request.config_path)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Invalid webhook config: {error}") from error
    try:
        delivery = export_report_via_webhook(
            report=report,
            destination_url=request.destination_url,
            audit_log_path=Path(job.artifact_dir or "artifacts/pipeline")
            / "exports"
            / "webhook_deliveries.jsonl",
            config=WebhookExportConfig(
                timeout_seconds=settings.timeout_seconds,
                max_retries=settings.max_retries,
                retry_backoff_seconds=settings.retry_backoff_seconds,
            ),
        )
    except WebhookExportError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ReportWebhookExportResponse(
        job_id=job_id,
        incident_id=incident_id,
        delivery_id=delivery.delivery_id,
        status=delivery.status,
        attempts=delivery.attempts,
        payload_id=delivery.payload_id,
    )


@app.get(
    "/incidents",
    response_model=IncidentListResponse,
    summary="List generated incident candidates",
    responses={404: {"model": ErrorResponse}},
)
def list_incidents(
    job_store: Annotated[AnalysisJobStore, Depends(get_job_store)],
    job_id: Annotated[str | None, Query(description="Optional job id filter.")] = None,
) -> IncidentListResponse:
    """List incidents for one job or all jobs."""

    if job_id:
        job = job_store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return IncidentListResponse(incidents=job.incidents)

    incidents: list[CorrelatedIncidentCandidate] = []
    for job in job_store.list():
        incidents.extend(job.incidents)
    return IncidentListResponse(incidents=incidents)


@app.get(
    "/anomalies",
    response_model=AnomalyListResponse,
    summary="List generated anomalies",
    responses={404: {"model": ErrorResponse}},
)
def list_anomalies(
    job_store: Annotated[AnalysisJobStore, Depends(get_job_store)],
    job_id: Annotated[str | None, Query(description="Optional job id filter.")] = None,
) -> AnomalyListResponse:
    """List anomalies for one job or all jobs."""

    if job_id:
        job = job_store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return AnomalyListResponse(anomalies=job.anomalies)

    anomalies: list[AnomalyCandidate] = []
    for job in job_store.list():
        anomalies.extend(job.anomalies)
    return AnomalyListResponse(anomalies=anomalies)


def _status_response(job: AnalysisJobRecord) -> AnalysisJobStatusResponse:
    return AnalysisJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        run_id=job.run_id,
        artifact_dir=job.artifact_dir,
        error=job.error,
    )


def _load_incidents(artifact_dir: str) -> list[CorrelatedIncidentCandidate]:
    path = Path(artifact_dir) / "incidents" / "incidents.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("incidents", [])
    if not isinstance(rows, list):
        return []
    return [CorrelatedIncidentCandidate.model_validate(item) for item in rows]


def _load_anomalies(artifact_dir: str) -> list[AnomalyCandidate]:
    path = Path(artifact_dir) / "anomalies" / "anomalies.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("anomalies", [])
    if not isinstance(rows, list):
        return []
    return [AnomalyCandidate.model_validate(item) for item in rows]
