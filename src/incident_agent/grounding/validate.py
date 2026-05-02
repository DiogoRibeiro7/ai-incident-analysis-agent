"""Grounding validation logic for report claims against evidence."""

from __future__ import annotations

import re

from incident_agent.core.settings import GroundingConfig
from incident_agent.knowledge.retrieval import RetrievedSnippet
from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.schemas.grounding import GroundingClaimAssessment, GroundingSummary
from incident_agent.schemas.rca import EvidenceBundle, RootCauseHypothesis

_TOKEN_RE = re.compile(r"[a-z0-9_.-]+")


def validate_report_grounding(
    *,
    report: FinalIncidentReport,
    evidence_bundle: EvidenceBundle,
    root_cause_hypothesis: RootCauseHypothesis,
    retrieved_context: list[RetrievedSnippet],
    config: GroundingConfig,
) -> GroundingSummary:
    """Validate report claims against known evidence and retrieved context."""

    claims = _extract_claims(report)
    supports = _build_support_entries(evidence_bundle, root_cause_hypothesis, retrieved_context)

    assessments: list[GroundingClaimAssessment] = []
    for claim in claims:
        claim_tokens = _tokens(claim)
        matched_ids: list[str] = []

        for support_id, support_text in supports:
            support_tokens = _tokens(support_text)
            if not support_tokens:
                continue
            overlap = _overlap_ratio(claim_tokens, support_tokens)
            if overlap >= config.minimum_support_overlap:
                matched_ids.append(support_id)

        supported = bool(matched_ids)
        assessments.append(
            GroundingClaimAssessment(
                claim=claim,
                supported=supported,
                support_ids=matched_ids,
                reason="matched_support" if supported else "insufficient_evidence_overlap",
            )
        )

    supported_claims = sum(1 for item in assessments if item.supported)
    unsupported_claims = len(assessments) - supported_claims
    passed = unsupported_claims == 0 if config.policy == "fail" else True
    return GroundingSummary(
        incident_id=report.incident_id,
        policy=config.policy,
        passed=passed,
        total_claims=len(assessments),
        supported_claims=supported_claims,
        unsupported_claims=unsupported_claims,
        claims=assessments,
    )


def _extract_claims(report: FinalIncidentReport) -> list[str]:
    claims: list[str] = []
    claims.extend(item.strip() for item in report.facts if item.strip())
    claims.extend(item.strip() for item in report.inferences if item.strip())
    return claims


def _build_support_entries(
    evidence_bundle: EvidenceBundle,
    root_cause_hypothesis: RootCauseHypothesis,
    retrieved_context: list[RetrievedSnippet],
) -> list[tuple[str, str]]:
    supports: list[tuple[str, str]] = []
    for index, evidence in enumerate(evidence_bundle.ranked_evidence, start=1):
        support_id = f"evidence-{index}"
        support_text = (
            f"{evidence.affected_service} {evidence.anomaly_type} "
            f"observed {evidence.observed_value} baseline {evidence.baseline_value} "
            f"{evidence.evidence_summary}"
        )
        supports.append((support_id, support_text))

    supports.append(
        (
            "hypothesis",
            (
                f"root cause {root_cause_hypothesis.suspected_root_cause_service} "
                f"confidence {root_cause_hypothesis.confidence_score} "
                f"{root_cause_hypothesis.rationale}"
            ),
        )
    )

    for snippet in retrieved_context:
        supports.append((snippet.citation_id, snippet.content))

    return supports


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if len(token) > 1}


def _overlap_ratio(claim_tokens: set[str], support_tokens: set[str]) -> float:
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & support_tokens) / float(len(claim_tokens))
