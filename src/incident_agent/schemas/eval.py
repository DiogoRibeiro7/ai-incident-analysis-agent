"""Schemas for evaluation harness inputs and outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BenchmarkScenario(BaseModel):
    """Benchmark scenario definition."""

    scenario_id: str
    description: str
    logs_path: str
    metrics_path: str
    expected_root_cause: str | None = None
    expected_impacted_services: list[str] = Field(default_factory=list)
    expected_min_incidents: int = 1


class EvaluationMetrics(BaseModel):
    """Evaluation dimensions for one mode/scenario run."""

    root_cause_correctness: float
    impacted_service_correctness: float
    factual_grounding: float
    hallucination_rate: float
    report_completeness: float
    latency_seconds: float
    token_usage: int | None = None


class EvaluationRunRecord(BaseModel):
    """One evaluation run record for scenario + mode."""

    scenario_id: str
    mode: str
    success: bool
    error: str | None = None
    predicted_root_cause: str | None = None
    predicted_impacted_services: list[str] = Field(default_factory=list)
    incident_count: int = 0
    metrics: EvaluationMetrics


class EvaluationSummary(BaseModel):
    """Aggregated metrics for a mode."""

    mode: str
    runs: int
    success_rate: float
    root_cause_correctness: float
    impacted_service_correctness: float
    factual_grounding: float
    hallucination_rate: float
    report_completeness: float
    latency_seconds: float


class EvaluationResult(BaseModel):
    """Full evaluation result and artifact pointers."""

    run_id: str
    artifact_dir: str
    records: list[EvaluationRunRecord] = Field(default_factory=list)
    summaries: list[EvaluationSummary] = Field(default_factory=list)
