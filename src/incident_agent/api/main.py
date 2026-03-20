"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from incident_agent.agents.incident_agent import IncidentAnalysisAgent
from incident_agent.llm.mock import MockLLMClient
from incident_agent.schemas.events import LogEvent, MetricPoint
from incident_agent.schemas.report import IncidentReport

app = FastAPI(title="AI Incident Analysis Agent", version="0.1.0")


class AnalyzeRequest(BaseModel):
    """Request schema for ad hoc incident analysis."""

    logs: list[LogEvent]
    metrics: list[MetricPoint]


class AnalyzeResponse(BaseModel):
    """Response schema for incident analysis."""

    reports: list[IncidentReport]


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint."""

    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a batch of logs and metrics."""

    agent = IncidentAnalysisAgent(llm_client=MockLLMClient())
    reports = agent.analyze(logs=request.logs, metrics=request.metrics)
    return AnalyzeResponse(reports=reports)
