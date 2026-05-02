"""Prompt rendering utilities for structured RCA artifacts."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from incident_agent.knowledge.retrieval import RetrievedSnippet
from incident_agent.prompts.templates import (
    ENGINEERING_HANDOFF_TEMPLATE,
    EXECUTIVE_SUMMARY_TEMPLATE,
    INCIDENT_SUMMARY_TEMPLATE,
    REMEDIATION_SUGGESTIONS_TEMPLATE,
    ROOT_CAUSE_EXPLANATION_TEMPLATE,
)
from incident_agent.schemas.rca import EvidenceBundle, IncidentSummaryFeatures, RootCauseHypothesis

TemplateName = Literal[
    "incident_summary",
    "root_cause_explanation",
    "executive_summary",
    "engineering_handoff",
    "remediation_suggestions",
]


class PromptRenderContext(BaseModel):
    """Structured prompt input derived from RCA artifacts."""

    incident_id: str
    evidence_bundle: EvidenceBundle
    summary_features: IncidentSummaryFeatures
    root_cause_hypothesis: RootCauseHypothesis
    retrieved_context: list[RetrievedSnippet] = Field(default_factory=list)


def render_prompt(template: TemplateName, context: PromptRenderContext) -> str:
    """Render one prompt template for a given RCA context."""

    template_text = _template_text(template)
    payload = _build_payload(context)
    return f"{template_text}\n\nEvidence payload:\n{payload}"


def render_all_prompts(context: PromptRenderContext) -> dict[TemplateName, str]:
    """Render all incident analysis prompt templates for a context."""

    templates: tuple[TemplateName, ...] = (
        "incident_summary",
        "root_cause_explanation",
        "executive_summary",
        "engineering_handoff",
        "remediation_suggestions",
    )
    return {name: render_prompt(name, context) for name in templates}


def _template_text(template: TemplateName) -> str:
    if template == "incident_summary":
        return INCIDENT_SUMMARY_TEMPLATE
    if template == "root_cause_explanation":
        return ROOT_CAUSE_EXPLANATION_TEMPLATE
    if template == "executive_summary":
        return EXECUTIVE_SUMMARY_TEMPLATE
    if template == "engineering_handoff":
        return ENGINEERING_HANDOFF_TEMPLATE
    if template == "remediation_suggestions":
        return REMEDIATION_SUGGESTIONS_TEMPLATE
    raise ValueError(f"Unsupported template: {template}")


def _build_payload(context: PromptRenderContext) -> str:
    payload = {
        "incident_id": context.incident_id,
        "evidence_bundle": context.evidence_bundle.model_dump(mode="json"),
        "summary_features": context.summary_features.model_dump(mode="json"),
        "root_cause_hypothesis": context.root_cause_hypothesis.model_dump(mode="json"),
        "retrieved_context": [
            snippet.model_dump(mode="json") for snippet in context.retrieved_context
        ],
    }
    return json.dumps(payload, indent=2)
