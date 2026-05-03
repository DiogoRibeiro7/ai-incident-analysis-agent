"""Schemas for evaluation harness inputs and outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

SyntheticScenarioType = Literal[
    "latency_degradation",
    "error_burst",
    "dependency_cascade",
    "traffic_drop",
    "resource_exhaustion",
    "partial_outage",
]


class SyntheticScenarioGeneratorConfig(BaseModel):
    """Config for synthetic benchmark generation."""

    scenario_type: SyntheticScenarioType
    root_cause_service: str
    impacted_services: list[str] = Field(default_factory=list)
    supporting_services: list[str] = Field(
        default_factory=lambda: ["api-service", "checkout-service", "gateway-service"]
    )
    start_time: datetime = datetime(2026, 3, 20, 11, 0, 0, tzinfo=UTC)
    duration_minutes: int = 30
    interval_minutes: int = 5
    seed: int = 7


class BenchmarkScenario(BaseModel):
    """Benchmark scenario definition."""

    scenario_id: str
    description: str
    logs_path: str
    metrics_path: str
    metadata_path: str | None = None
    expected_root_cause: str | None = None
    expected_impacted_services: list[str] = Field(default_factory=list)
    expected_min_incidents: int = 1
    retrieval_source_paths: list[str] = Field(default_factory=list)
    generator: SyntheticScenarioGeneratorConfig | None = None


class EvaluationMetrics(BaseModel):
    """Evaluation dimensions for one mode/scenario run."""

    root_cause_correctness: float
    impacted_service_correctness: float
    factual_grounding: float
    citation_coverage: float
    retrieval_relevance: float = 0.0
    hallucination_rate: float
    report_completeness: float
    latency_seconds: float
    token_usage: int | None = None
    estimated_cost_usd: float | None = None


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
    citation_coverage: float
    retrieval_relevance: float = 0.0
    hallucination_rate: float
    report_completeness: float
    latency_seconds: float
    average_token_usage: float | None = None
    total_estimated_cost_usd: float | None = None


class EvaluationResult(BaseModel):
    """Full evaluation result and artifact pointers."""

    run_id: str
    artifact_dir: str
    records: list[EvaluationRunRecord] = Field(default_factory=list)
    summaries: list[EvaluationSummary] = Field(default_factory=list)


class EvaluationRegressionThresholds(BaseModel):
    """Allowed regression thresholds for candidate vs baseline summaries."""

    success_rate_drop_max: float = 0.0
    root_cause_correctness_drop_max: float = 0.02
    impacted_service_correctness_drop_max: float = 0.02
    factual_grounding_drop_max: float = 0.02
    citation_coverage_drop_max: float = 0.02
    report_completeness_drop_max: float = 0.02
    hallucination_rate_increase_max: float = 0.05


class EvaluationComparisonFinding(BaseModel):
    """One regression finding for one mode/metric."""

    mode: str
    metric: str
    baseline_value: float
    candidate_value: float
    delta: float
    threshold: float


class EvaluationComparisonResult(BaseModel):
    """Comparison output for baseline vs candidate evaluation summaries."""

    passed: bool
    baseline_summary_path: str
    candidate_summary_path: str
    findings: list[EvaluationComparisonFinding] = Field(default_factory=list)
