"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from incident_agent.agents.incident_agent import IncidentAnalysisAgent
from incident_agent.llm.factory import create_provider, load_llm_config
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.pipeline import PipelineRunResult
from incident_agent.schemas.report import IncidentReport
from incident_agent.services.pipeline import run_pipeline_from_files

app = FastAPI(title="AI Incident Analysis Agent", version="0.1.0")


class AnalyzeRequest(BaseModel):
    """Request schema for ad hoc incident analysis."""

    logs: list[LogEvent]
    metrics: list[MetricPoint]


class AnalyzeResponse(BaseModel):
    """Response schema for incident analysis."""

    reports: list[IncidentReport]


class PipelineAnalyzeRequest(BaseModel):
    """Request schema for full file-based pipeline execution."""

    logs_path: str
    metrics_path: str
    config_path: str = "configs/default.yaml"
    artifact_root: str = "artifacts/pipeline"
    bucket_size_minutes: int | None = None


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint."""

    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a batch of logs and metrics."""

    config = load_llm_config()
    provider = create_provider(config)
    agent = IncidentAnalysisAgent(provider=provider, report_model=config.report_model)
    reports = agent.analyze(logs=request.logs, metrics=request.metrics)
    return AnalyzeResponse(reports=reports)


@app.post("/analyze-pipeline", response_model=PipelineRunResult)
def analyze_pipeline(request: PipelineAnalyzeRequest) -> PipelineRunResult:
    """Run full file-based pipeline and persist output artifacts."""

    return run_pipeline_from_files(
        log_path=request.logs_path,
        metric_path=request.metrics_path,
        config_path=request.config_path,
        artifact_root=request.artifact_root,
        bucket_size_minutes=request.bucket_size_minutes,
    )
