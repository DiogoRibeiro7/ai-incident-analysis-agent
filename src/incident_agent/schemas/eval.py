"""Schemas for evaluation harness inputs and outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

SyntheticScenarioType = Literal[
    "healthy_stable",
    "healthy_noisy",
    "normal_traffic_variability",
    "transient_latency_spike",
    "latency_degradation",
    "gradual_latency_drift",
    "error_burst",
    "persistent_error_rate",
    "error_logs_only",
    "metrics_only_degradation",
    "cpu_saturation",
    "memory_saturation",
    "resource_anomaly_no_impact",
    "dependency_cascade",
    "upstream_root_cause",
    "downstream_symptoms",
    "unrelated_simultaneous",
    "traffic_drop",
    "traffic_disappearance",
    "isolated_low_volume_bucket",
    "resource_exhaustion",
    "partial_outage",
    "heartbeat_loss",
    "temporary_unavailability",
    "missing_observability",
    "ambiguous_root_causes",
    "contradictory_telemetry",
    "insufficient_evidence",
    "missing_logs",
    "missing_metrics",
    "sparse_observations",
]


class EvaluationMode(StrEnum):
    """Supported evaluation execution modes."""

    HEURISTIC_ONLY = "heuristic-only"
    MOCK_LLM_NO_RETRIEVAL = "mock-llm-no-retrieval"
    MOCK_LLM_RETRIEVAL = "mock-llm-retrieval"
    REAL_LLM_NO_RETRIEVAL = "real-llm-no-retrieval"
    REAL_LLM_RETRIEVAL = "real-llm-retrieval"


DEFAULT_EVALUATION_MODES: tuple[EvaluationMode, ...] = (
    EvaluationMode.HEURISTIC_ONLY,
    EvaluationMode.MOCK_LLM_NO_RETRIEVAL,
    EvaluationMode.MOCK_LLM_RETRIEVAL,
)

REAL_LLM_EVALUATION_MODES: tuple[EvaluationMode, ...] = (
    EvaluationMode.REAL_LLM_NO_RETRIEVAL,
    EvaluationMode.REAL_LLM_RETRIEVAL,
)


def evaluation_modes(*, include_real_llm: bool = False) -> tuple[EvaluationMode, ...]:
    """Return the canonical ordered modes for evaluation runs."""

    if include_real_llm:
        return DEFAULT_EVALUATION_MODES + REAL_LLM_EVALUATION_MODES
    return DEFAULT_EVALUATION_MODES


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
    incident_expected: bool = True
    expected_root_cause: str | None = None
    allowed_root_causes: list[str] = Field(default_factory=list)
    expected_impacted_services: list[str] = Field(default_factory=list)
    expected_anomaly_types: list[str] = Field(default_factory=list)
    expected_min_incidents: int = 1
    expected_max_incidents: int | None = None
    retrieval_source_paths: list[str] = Field(default_factory=list)
    generator: SyntheticScenarioGeneratorConfig | None = None


class EvaluationMetrics(BaseModel):
    """Evaluation dimensions for one mode/scenario run."""

    incident_detected: bool = False
    incident_expectation_correctness: float = 0.0
    incident_count_correctness: float = 0.0
    incident_true_positive: int = 0
    incident_false_positive: int = 0
    incident_false_negative: int = 0
    incident_true_negative: int = 0
    root_cause_correctness: float
    impacted_service_correctness: float
    impacted_service_precision: float = 0.0
    impacted_service_recall: float = 0.0
    impacted_service_f1: float = 0.0
    anomaly_type_recall: float = 0.0
    service_entity_precision: float
    unexpected_service_mention_rate: float
    citation_coverage: float
    retrieval_relevance: float = 0.0
    factual_claim_count: int = 0
    supported_factual_claim_count: int = 0
    unsupported_factual_claim_count: int = 0
    contradictory_factual_claim_count: int = 0
    factual_claim_support_rate: float = 0.0
    unsupported_factual_claim_rate: float = 0.0
    contradictory_factual_claim_rate: float = 0.0
    report_completeness: float
    latency_seconds: float
    token_usage: int | None = None
    estimated_cost_usd: float | None = None


class EvaluationRunRecord(BaseModel):
    """One evaluation run record for scenario + mode."""

    scenario_id: str
    mode: EvaluationMode
    success: bool
    error: str | None = None
    predicted_root_cause: str | None = None
    predicted_impacted_services: list[str] = Field(default_factory=list)
    predicted_anomaly_types: list[str] = Field(default_factory=list)
    incident_count: int = 0
    metrics: EvaluationMetrics


class EvaluationSummary(BaseModel):
    """Aggregated metrics for a mode."""

    mode: EvaluationMode
    runs: int
    success_rate: float
    incident_precision: float = 0.0
    incident_recall: float = 0.0
    incident_f1: float = 0.0
    incident_false_positive_rate: float = 0.0
    incident_count_correctness: float = 0.0
    incident_true_positive: int = 0
    incident_false_positive: int = 0
    incident_false_negative: int = 0
    incident_true_negative: int = 0
    root_cause_correctness: float
    impacted_service_correctness: float
    impacted_service_precision: float = 0.0
    impacted_service_recall: float = 0.0
    impacted_service_f1: float = 0.0
    anomaly_type_recall: float = 0.0
    service_entity_precision: float
    unexpected_service_mention_rate: float
    citation_coverage: float
    retrieval_relevance: float = 0.0
    factual_claim_count: int = 0
    supported_factual_claim_count: int = 0
    unsupported_factual_claim_count: int = 0
    contradictory_factual_claim_count: int = 0
    factual_claim_support_rate: float = 0.0
    unsupported_factual_claim_rate: float = 0.0
    contradictory_factual_claim_rate: float = 0.0
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
    incident_f1_drop_max: float = 0.02
    incident_false_positive_rate_increase_max: float = 0.02
    incident_count_correctness_drop_max: float = 0.02
    root_cause_correctness_drop_max: float = 0.02
    impacted_service_correctness_drop_max: float = 0.02
    impacted_service_f1_drop_max: float = 0.02
    anomaly_type_recall_drop_max: float = 0.02
    service_entity_precision_drop_max: float = 0.02
    unexpected_service_mention_rate_increase_max: float = 0.05
    factual_claim_support_rate_drop_max: float = 0.02
    unsupported_factual_claim_rate_increase_max: float = 0.05
    contradictory_factual_claim_rate_increase_max: float = 0.0
    citation_coverage_drop_max: float = 0.02
    report_completeness_drop_max: float = 0.02


class EvaluationComparisonFinding(BaseModel):
    """One regression finding for one mode/metric."""

    mode: EvaluationMode
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
