"""Schemas for end-to-end pipeline execution results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from incident_agent.schemas.final_report import FinalIncidentReport


class PipelineFailureSummary(BaseModel):
    """One degraded or failed condition encountered during execution."""

    stage: str
    message: str
    fatal: bool = False


class PipelineRunResult(BaseModel):
    """Summary of one pipeline run and generated final reports."""

    run_id: str
    artifact_dir: str
    normalized_event_count: int
    anomaly_count: int
    incident_count: int
    hypothesis_count: int
    final_report_count: int
    degraded: bool = False
    completed_stages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failure_summaries: list[PipelineFailureSummary] = Field(default_factory=list)
    used_intermediate_cache: bool = False
    used_llm_cache: bool = False
    final_reports: list[FinalIncidentReport] = Field(default_factory=list)
