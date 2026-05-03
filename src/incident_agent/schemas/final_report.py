"""Structured schema for final incident analysis reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

ReviewStatus = Literal["draft", "reviewed", "approved", "rejected"]


class ReportReviewEntry(BaseModel):
    """Audit entry for one report review transition."""

    from_status: ReviewStatus
    to_status: ReviewStatus
    reviewer: str
    note: str
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ClaimCitation(BaseModel):
    """Support mapping for one report claim."""

    claim: str
    support_ids: list[str] = Field(default_factory=list)


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
    citations: list[str] = Field(default_factory=list)
    claim_citations: list[ClaimCitation] = Field(default_factory=list)
    review_status: ReviewStatus = "draft"
    review_history: list[ReportReviewEntry] = Field(default_factory=list)
