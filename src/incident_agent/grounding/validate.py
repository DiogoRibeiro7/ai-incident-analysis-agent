"""Grounding validation logic for report claims against evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from incident_agent.core.settings import GroundingConfig
from incident_agent.knowledge.retrieval import RetrievedSnippet
from incident_agent.schemas.final_report import ClaimCitation, FinalIncidentReport
from incident_agent.schemas.grounding import (
    ClaimType,
    ClaimValidationStatus,
    GroundingClaimAssessment,
    GroundingSummary,
)
from incident_agent.schemas.rca import EvidenceBundle, RootCauseHypothesis

_TOKEN_RE = re.compile(r"[a-z0-9_.-]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_SERVICE_RE = re.compile(r"\b[a-z][a-z0-9-]*-service\b")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "then",
    "to",
    "with",
}
_ANOMALY_KEYWORDS: dict[str, set[str]] = {
    "latency_spike": {"latency", "slow", "slowness", "p95", "response"},
    "error_rate_spike": {"error", "errors", "failure", "failures", "5xx"},
    "cpu_anomaly": {"cpu"},
    "memory_anomaly": {"memory"},
    "traffic_drop": {"traffic", "request", "requests", "drop", "dropped"},
    "service_unavailability": {"availability", "unavailable", "outage", "down"},
}
_INFERENCE_TERMS = {
    "because",
    "caused",
    "cause",
    "causes",
    "due",
    "indicate",
    "indicates",
    "likely",
    "possible",
    "suggest",
    "suggests",
    "suspected",
}
_UNCERTAINTY_TERMS = {
    "ambiguity",
    "ambiguous",
    "uncertain",
    "uncertainty",
    "unknown",
    "unclear",
    "unconfirmed",
}
_RECOMMENDATION_STARTS = (
    "add ",
    "check ",
    "confirm ",
    "contain ",
    "create ",
    "harden ",
    "inspect ",
    "investigate ",
    "monitor ",
    "review ",
    "rollback ",
    "scale ",
    "verify ",
)
_FACTUAL_PREMISE_TERMS = {
    "after",
    "because",
    "caused",
    "causing",
    "due",
    "during",
    "observed",
    "since",
    "shows",
}


@dataclass(frozen=True)
class ExtractedClaim:
    claim_id: str
    text: str
    section: str
    claim_type: ClaimType
    requires_evidence: bool


@dataclass(frozen=True)
class SupportEntry:
    support_id: str
    text: str
    service: str | None = None
    anomaly_type: str | None = None


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
        status, support_ids, reason = _validate_claim(
            claim=claim,
            supports=supports,
            minimum_support_overlap=config.minimum_support_overlap,
        )
        assessments.append(
            GroundingClaimAssessment(
                claim_id=claim.claim_id,
                text=claim.text,
                section=claim.section,
                claim_type=claim.claim_type,
                status=status,
                supporting_evidence_ids=support_ids,
                reason=reason,
            )
        )

    supported_claims = sum(
        1 for item in assessments if item.status is ClaimValidationStatus.SUPPORTED
    )
    unsupported_claims = sum(
        1 for item in assessments if item.status is ClaimValidationStatus.UNSUPPORTED
    )
    contradictory_claims = sum(
        1 for item in assessments if item.status is ClaimValidationStatus.CONTRADICTORY
    )
    not_applicable_claims = sum(
        1 for item in assessments if item.status is ClaimValidationStatus.NOT_APPLICABLE
    )
    failed_claims = unsupported_claims + contradictory_claims
    passed = failed_claims == 0 if config.policy == "fail" else True
    return GroundingSummary(
        incident_id=report.incident_id,
        policy=config.policy,
        passed=passed,
        total_claims=len(assessments),
        supported_claims=supported_claims,
        unsupported_claims=unsupported_claims,
        contradictory_claims=contradictory_claims,
        not_applicable_claims=not_applicable_claims,
        claims=assessments,
    )


def build_claim_citations(
    *,
    report: FinalIncidentReport,
    evidence_bundle: EvidenceBundle,
    root_cause_hypothesis: RootCauseHypothesis,
    retrieved_context: list[RetrievedSnippet],
    minimum_support_overlap: float,
) -> list[ClaimCitation]:
    """Build machine-readable evidence mappings for facts and inferences."""

    claims = _extract_claims(report)
    supports = _build_support_entries(evidence_bundle, root_cause_hypothesis, retrieved_context)
    claim_citations: list[ClaimCitation] = []
    for claim in claims:
        if not claim.requires_evidence:
            continue
        _, support_ids, _ = _validate_claim(
            claim=claim,
            supports=supports,
            minimum_support_overlap=minimum_support_overlap,
        )
        claim_citations.append(ClaimCitation(claim=claim.text, support_ids=support_ids))
    return claim_citations


def _extract_claims(report: FinalIncidentReport) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    source_sections = [
        ("incident_summary", [report.incident_summary]),
        ("root_cause_explanation", [report.root_cause_explanation]),
        ("executive_summary", [report.executive_summary]),
        ("engineering_handoff", [report.engineering_handoff]),
        ("remediation_suggestions", report.remediation_suggestions),
        ("facts", report.facts),
        ("inferences", report.inferences),
        ("uncertainties", report.uncertainties),
    ]
    for section, values in source_sections:
        for value in values:
            for text in _split_claims(value):
                claim_type = _classify_claim(text=text, section=section)
                claims.append(
                    ExtractedClaim(
                        claim_id=f"{section}-{len(claims) + 1}",
                        text=text,
                        section=section,
                        claim_type=claim_type,
                        requires_evidence=_requires_evidence(
                            text=text,
                            section=section,
                            claim_type=claim_type,
                        ),
                    )
                )
    return claims


def _build_support_entries(
    evidence_bundle: EvidenceBundle,
    root_cause_hypothesis: RootCauseHypothesis,
    retrieved_context: list[RetrievedSnippet],
) -> list[SupportEntry]:
    supports: list[SupportEntry] = []
    for index, evidence in enumerate(evidence_bundle.ranked_evidence, start=1):
        support_id = f"evidence-{index}"
        support_text = (
            f"{evidence.affected_service} {evidence.anomaly_type} "
            f"observed {evidence.observed_value} baseline {evidence.baseline_value} "
            f"{evidence.evidence_summary} "
            f"{' '.join(sorted(_ANOMALY_KEYWORDS.get(evidence.anomaly_type, set())))}"
        )
        supports.append(
            SupportEntry(
                support_id=support_id,
                text=support_text,
                service=evidence.affected_service,
                anomaly_type=evidence.anomaly_type,
            )
        )

    supports.append(
        SupportEntry(
            support_id="hypothesis",
            text=(
                f"root cause {root_cause_hypothesis.suspected_root_cause_service} "
                f"confidence {root_cause_hypothesis.confidence_score} "
                f"impacted {' '.join(root_cause_hypothesis.impacted_downstream_services)} "
                f"{root_cause_hypothesis.rationale}"
            ),
            service=root_cause_hypothesis.suspected_root_cause_service,
        )
    )

    for snippet in retrieved_context:
        supports.append(SupportEntry(support_id=snippet.citation_id, text=snippet.content))

    return supports


def _validate_claim(
    *,
    claim: ExtractedClaim,
    supports: list[SupportEntry],
    minimum_support_overlap: float,
) -> tuple[ClaimValidationStatus, list[str], str]:
    if not claim.requires_evidence:
        return ClaimValidationStatus.NOT_APPLICABLE, [], "evidence_not_required"

    claim_tokens = _tokens(claim.text)
    claim_services = _services(claim.text)
    claim_anomaly_types = _anomaly_types(claim.text)
    matched_ids: list[str] = []

    for support in supports:
        support_tokens = _tokens(support.text)
        if not support_tokens:
            continue
        overlap = _overlap_ratio(claim_tokens, support_tokens)
        if overlap < minimum_support_overlap:
            continue
        if not _structured_support_matches(
            support=support,
            claim_services=claim_services,
            claim_anomaly_types=claim_anomaly_types,
        ):
            continue
        matched_ids.append(support.support_id)

    if matched_ids:
        return ClaimValidationStatus.SUPPORTED, matched_ids, "matched_support"

    if _contradicts_structured_evidence(
        claim_services=claim_services,
        claim_anomaly_types=claim_anomaly_types,
        supports=supports,
    ):
        return ClaimValidationStatus.CONTRADICTORY, [], "conflicts_with_structured_evidence"

    return ClaimValidationStatus.UNSUPPORTED, [], "insufficient_evidence_overlap"


def _split_claims(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    return [part.strip(" -\t") for part in _SENTENCE_SPLIT_RE.split(cleaned) if part.strip(" -\t")]


def _classify_claim(*, text: str, section: str) -> ClaimType:
    lowered = text.lower().strip()
    if section == "uncertainties" or any(term in lowered for term in _UNCERTAINTY_TERMS):
        return ClaimType.UNCERTAINTY
    if section == "facts":
        return ClaimType.FACT
    if section in {"inferences", "root_cause_explanation"}:
        return ClaimType.INFERENCE
    if section == "remediation_suggestions" or lowered.startswith(_RECOMMENDATION_STARTS):
        return ClaimType.RECOMMENDATION
    if any(term in lowered for term in _INFERENCE_TERMS):
        return ClaimType.INFERENCE
    return ClaimType.FACT


def _requires_evidence(*, text: str, section: str, claim_type: ClaimType) -> bool:
    if claim_type is ClaimType.UNCERTAINTY:
        return False
    if claim_type is ClaimType.RECOMMENDATION:
        lowered = text.lower()
        return section == "remediation_suggestions" and any(
            term in lowered for term in _FACTUAL_PREMISE_TERMS
        )
    return True


def _structured_support_matches(
    *,
    support: SupportEntry,
    claim_services: set[str],
    claim_anomaly_types: set[str],
) -> bool:
    if support.service and claim_services and support.service not in claim_services:
        return False
    if (
        support.anomaly_type
        and claim_anomaly_types
        and support.anomaly_type not in claim_anomaly_types
    ):
        return False
    return True


def _contradicts_structured_evidence(
    *,
    claim_services: set[str],
    claim_anomaly_types: set[str],
    supports: list[SupportEntry],
) -> bool:
    if not claim_services or not claim_anomaly_types:
        return False
    structured = [support for support in supports if support.service and support.anomaly_type]
    for anomaly_type in claim_anomaly_types:
        supported_services = {
            support.service
            for support in structured
            if support.anomaly_type == anomaly_type and support.service is not None
        }
        if supported_services and not claim_services & supported_services:
            return True
    return False


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if len(token) > 1 and token not in _STOPWORDS
    }


def _services(text: str) -> set[str]:
    return set(_SERVICE_RE.findall(text.lower()))


def _anomaly_types(text: str) -> set[str]:
    tokens = _tokens(text)
    return {
        anomaly_type
        for anomaly_type, keywords in _ANOMALY_KEYWORDS.items()
        if tokens & keywords or anomaly_type in tokens
    }


def _overlap_ratio(claim_tokens: set[str], support_tokens: set[str]) -> float:
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & support_tokens) / float(len(claim_tokens))
