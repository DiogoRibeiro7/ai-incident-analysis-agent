"""Structured schema for final incident analysis reports."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FinalIncidentReport(BaseModel):
    """Canonical structured final report schema."""

    incident_id: str
    incident_summary: str
    root_cause_explanation: str
    executive_summary: str
    engineering_handoff: str
    remediation_suggestions: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
