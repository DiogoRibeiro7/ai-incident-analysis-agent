"""Schemas for report grounding validation results."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

GroundingPolicy = Literal["warn", "fail"]


class ClaimType(StrEnum):
    """Classification for an extracted report claim."""

    FACT = "fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"
    UNCERTAINTY = "uncertainty"


class ClaimValidationStatus(StrEnum):
    """Evidence validation status for an extracted report claim."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTORY = "contradictory"
    NOT_APPLICABLE = "not_applicable"


class GroundingClaimAssessment(BaseModel):
    """Validation result for one report claim."""

    claim_id: str
    text: str
    section: str
    claim_type: ClaimType
    status: ClaimValidationStatus
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    reason: str


class GroundingSummary(BaseModel):
    """Grounding summary for one incident report."""

    incident_id: str
    policy: GroundingPolicy
    passed: bool
    total_claims: int
    supported_claims: int
    unsupported_claims: int
    contradictory_claims: int = 0
    not_applicable_claims: int = 0
    claims: list[GroundingClaimAssessment] = Field(default_factory=list)
