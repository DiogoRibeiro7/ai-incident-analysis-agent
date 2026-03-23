from __future__ import annotations

import json

from incident_agent.export.serializers import (
    serialize_report_as_html,
    serialize_report_as_json,
    serialize_report_as_markdown,
)
from incident_agent.schemas.final_report import FinalIncidentReport


def _report() -> FinalIncidentReport:
    return FinalIncidentReport(
        incident_id="inc-20260320T110000Z-001",
        incident_summary="Checkout latency degraded for 15 minutes.",
        root_cause_explanation="Gateway timeout cascade increased checkout latency and errors.",
        executive_summary=(
            "Customer-facing checkout performance degraded "
            "with partial request loss."
        ),
        engineering_handoff=(
            "Review upstream timeout changes and dependency "
            "saturation around 11:15 UTC."
        ),
        remediation_suggestions=["Rollback timeout change", "Add circuit breaker protections"],
        facts=["Latency rose from 120ms baseline to 1450ms", "Error rate peaked at 18%"],
        inferences=["Gateway-service is the dominant upstream trigger"],
        uncertainties=["Exact rollout timestamp not confirmed"],
    )


def test_serialize_report_as_json_preserves_canonical_schema() -> None:
    payload = json.loads(serialize_report_as_json(_report()))

    assert payload["incident_id"] == "inc-20260320T110000Z-001"
    assert payload["remediation_suggestions"] == [
        "Rollback timeout change",
        "Add circuit breaker protections",
    ]


def test_serialize_report_as_markdown_renders_headings() -> None:
    markdown = serialize_report_as_markdown(_report())

    assert markdown.startswith("# Incident Report:")
    assert "## Root Cause Explanation" in markdown
    assert "- Rollback timeout change" in markdown


def test_serialize_report_as_html_renders_standalone_document() -> None:
    html = serialize_report_as_html(_report())

    assert html.startswith("<!DOCTYPE html>")
    assert "<html lang=\"en\">" in html
    assert "AI Incident Analysis" in html
    assert "Checkout latency degraded for 15 minutes." in html
