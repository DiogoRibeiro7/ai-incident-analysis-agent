"""Schemas for root-cause analysis intermediate artifacts."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from incident_agent.schemas.anomaly import AnomalyCandidate


class EvidenceBundle(BaseModel):
    """Ranked evidence bundle for one incident candidate."""

    incident_id: str
    ranked_evidence: list[AnomalyCandidate] = Field(default_factory=list)
    contributing_signals: list[str] = Field(default_factory=list)
    impacted_downstream_services: list[str] = Field(default_factory=list)
    unresolved_ambiguities: list[str] = Field(default_factory=list)


class IncidentSummaryFeatures(BaseModel):
    """Summarized feature snapshot for one incident candidate."""

    incident_id: str
    total_evidence: int
    impacted_services: list[str] = Field(default_factory=list)
    anomaly_type_counts: dict[str, int] = Field(default_factory=dict)
    service_evidence_counts: dict[str, int] = Field(default_factory=dict)
    average_severity: float
    peak_severity: float


class RootCauseHypothesis(BaseModel):
    """Heuristic root-cause hypothesis for one incident candidate."""

    model_config = ConfigDict(populate_by_name=True)

    incident_id: str
    suspected_root_cause_service: str
    root_cause_support: float = Field(
        validation_alias=AliasChoices("root_cause_support", "confidence_score"),
        description=(
            "Relative support score for the selected root-cause service: "
            "top candidate score divided by the sum of all candidate scores."
        ),
    )
    contributing_signals: list[str] = Field(default_factory=list)
    impacted_downstream_services: list[str] = Field(default_factory=list)
    unresolved_ambiguities: list[str] = Field(default_factory=list)
    rationale: str

    @property
    def confidence_score(self) -> float:
        """Backward-compatible alias for older serialized RCA artifacts."""

        return self.root_cause_support


class RCAResult(BaseModel):
    """Full RCA output collection."""

    bundles: list[EvidenceBundle] = Field(default_factory=list)
    summaries: list[IncidentSummaryFeatures] = Field(default_factory=list)
    hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
