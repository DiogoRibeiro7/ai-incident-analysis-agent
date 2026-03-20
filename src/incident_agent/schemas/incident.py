"""Schemas for correlated incident candidates."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from incident_agent.schemas.anomaly import AnomalyCandidate


class CorrelatedIncidentCandidate(BaseModel):
    """Incident candidate produced by anomaly correlation."""

    incident_id: str
    start_time: datetime
    end_time: datetime
    impacted_services: list[str] = Field(default_factory=list)
    suspected_primary_service: str
    evidence: list[AnomalyCandidate] = Field(default_factory=list)
    correlation_score: float


class IncidentCorrelationResult(BaseModel):
    """Collection of correlated incident candidates."""

    incidents: list[CorrelatedIncidentCandidate] = Field(default_factory=list)
