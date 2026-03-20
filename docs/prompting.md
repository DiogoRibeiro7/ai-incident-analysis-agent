# Prompting Strategy

## Goal

Render modular, grounded prompts from structured RCA artifacts instead of free-form raw context.

## Templates

Template definitions:
- `src/incident_agent/prompts/templates.py`

Templates included:
- incident summary
- root-cause explanation
- executive summary
- engineering handoff report
- remediation suggestions

## Rendering layer

Renderer:
- `src/incident_agent/prompts/renderer.py`

Key API:
- `PromptRenderContext`
- `render_prompt(...)`
- `render_all_prompts(...)`

The context requires:
- `EvidenceBundle`
- `IncidentSummaryFeatures`
- `RootCauseHypothesis`

This keeps prompt generation testable without any provider calls.

## Hallucination guardrails

All templates explicitly enforce:
- use only provided evidence,
- do not invent metrics/services/timestamps/events,
- include uncertainty when evidence is insufficient,
- separate facts from inference.

## Output schema

Canonical final report schema:
- `src/incident_agent/schemas/final_report.py`
- `FinalIncidentReport`

This schema is used to validate report structure independently from provider behavior.
