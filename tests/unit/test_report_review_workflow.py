from __future__ import annotations

import pytest

from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.workflow.review import ReviewTransitionError, transition_report_review


def _report() -> FinalIncidentReport:
    return FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="summary",
        root_cause_explanation="cause",
        executive_summary="exec",
        engineering_handoff="handoff",
    )


def test_review_transition_allows_draft_to_reviewed() -> None:
    report = _report()
    transition_report_review(
        report,
        to_status="reviewed",
        reviewer="alice",
        note="validated evidence mapping",
    )
    assert report.review_status == "reviewed"
    assert len(report.review_history) == 1


def test_review_transition_rejects_invalid_path() -> None:
    report = _report()
    with pytest.raises(ReviewTransitionError):
        transition_report_review(
            report,
            to_status="approved",
            reviewer="alice",
            note="skip state",
        )
