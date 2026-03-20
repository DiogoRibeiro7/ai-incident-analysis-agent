"""Schemas for final incident reports."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Evidence used to support the generated report."""

    kind: str
    timestamp: str
    content: str


class IncidentReport(BaseModel):
    """Structured report returned by the agent."""

    title: str
    severity: str
    impacted_service: str
    incident_summary: str
    likely_root_causes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
