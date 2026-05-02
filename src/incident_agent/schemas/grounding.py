"""Schemas for report grounding validation results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

GroundingPolicy = Literal["warn", "fail"]


class GroundingClaimAssessment(BaseModel):
    """Validation result for one report claim."""

    claim: str
    supported: bool
    support_ids: list[str] = Field(default_factory=list)
    reason: str


class GroundingSummary(BaseModel):
    """Grounding summary for one incident report."""

    incident_id: str
    policy: GroundingPolicy
    passed: bool
    total_claims: int
    supported_claims: int
    unsupported_claims: int
    claims: list[GroundingClaimAssessment] = Field(default_factory=list)
