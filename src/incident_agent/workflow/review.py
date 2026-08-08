"""Review lifecycle transitions for final incident reports."""

from __future__ import annotations

from incident_agent.schemas.final_report import (
    FinalIncidentReport,
    ReportReviewEntry,
    ReviewStatus,
)

_ALLOWED_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    "draft": {"reviewed"},
    "reviewed": {"approved", "rejected"},
    "approved": set(),
    "rejected": set(),
}


class ReviewTransitionError(ValueError):
    """Raised when a review transition is invalid."""


def transition_report_review(
    report: FinalIncidentReport,
    *,
    to_status: ReviewStatus,
    reviewer: str,
    note: str,
) -> FinalIncidentReport:
    """Apply a review status transition with audit metadata."""

    cleaned_reviewer = reviewer.strip()
    cleaned_note = note.strip()
    if not cleaned_reviewer:
        raise ReviewTransitionError("Reviewer must be non-empty.")
    if not cleaned_note:
        raise ReviewTransitionError("Review note must be non-empty.")

    from_status = report.review_status
    allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ReviewTransitionError(f"Invalid review transition: {from_status} -> {to_status}.")
    report.review_status = to_status
    report.review_history.append(
        ReportReviewEntry(
            from_status=from_status,
            to_status=to_status,
            reviewer=cleaned_reviewer,
            note=cleaned_note,
        )
    )
    return report
