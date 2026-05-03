from __future__ import annotations

import pytest
from pydantic import ValidationError

from incident_agent.schemas.final_report import FinalIncidentReport


def test_final_report_schema_validates_expected_payload() -> None:
    report = FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="Checkout latency degraded for 5 minutes.",
        root_cause_explanation="Checkout service latency spike after upstream slowdown.",
        executive_summary="Short incident with elevated checkout latency and partial impact.",
        engineering_handoff="Inspect checkout dependency timeouts and rollback recent config.",
        remediation_suggestions=["Rollback timeout config", "Add latency SLO alerts"],
        facts=["Latency reached 1900ms", "Error rate increased to 0.22"],
        inferences=["Likely checkout dependency bottleneck"],
        uncertainties=["No deploy metadata was provided"],
    )

    assert report.incident_id == "inc-1"
    assert report.remediation_suggestions
    assert report.review_status == "draft"
    assert report.claim_citations == []
    assert report.review_history == []


def test_final_report_schema_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        FinalIncidentReport.model_validate({"incident_id": "inc-1"})
