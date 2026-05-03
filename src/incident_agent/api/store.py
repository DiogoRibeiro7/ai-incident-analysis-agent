"""In-memory job storage for API analysis workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from incident_agent.schemas.anomaly import AnomalyCandidate
from incident_agent.schemas.final_report import FinalIncidentReport, ReviewStatus
from incident_agent.schemas.incident import CorrelatedIncidentCandidate
from incident_agent.workflow.review import transition_report_review

JobStatus = Literal["submitted", "completed", "failed"]


class AnalysisJobRecord(BaseModel):
    """Stored record for one analysis job."""

    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    run_id: str | None = None
    artifact_dir: str | None = None
    error: str | None = None
    reports: list[FinalIncidentReport] = Field(default_factory=list)
    incidents: list[CorrelatedIncidentCandidate] = Field(default_factory=list)
    anomalies: list[AnomalyCandidate] = Field(default_factory=list)


class AnalysisJobStore:
    """Simple in-memory store for local file-based API workflows."""

    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJobRecord] = {}

    def create_submitted_job(self) -> AnalysisJobRecord:
        """Create a submitted job record."""

        now = datetime.now(UTC)
        record = AnalysisJobRecord(
            job_id=f"job-{uuid4().hex[:12]}",
            status="submitted",
            created_at=now,
            updated_at=now,
        )
        self._jobs[record.job_id] = record
        return record

    def mark_completed(
        self,
        *,
        job_id: str,
        run_id: str,
        artifact_dir: str,
        reports: list[FinalIncidentReport],
        incidents: list[CorrelatedIncidentCandidate],
        anomalies: list[AnomalyCandidate],
    ) -> AnalysisJobRecord:
        """Mark job as completed and attach generated artifacts."""

        existing = self._jobs[job_id]
        existing.status = "completed"
        existing.updated_at = datetime.now(UTC)
        existing.run_id = run_id
        existing.artifact_dir = artifact_dir
        existing.reports = reports
        existing.incidents = incidents
        existing.anomalies = anomalies
        self._jobs[job_id] = existing
        return existing

    def mark_failed(self, *, job_id: str, error: str) -> AnalysisJobRecord:
        """Mark job as failed with an error message."""

        existing = self._jobs[job_id]
        existing.status = "failed"
        existing.updated_at = datetime.now(UTC)
        existing.error = error
        self._jobs[job_id] = existing
        return existing

    def get(self, job_id: str) -> AnalysisJobRecord | None:
        """Return job record by id if present."""

        return self._jobs.get(job_id)

    def transition_report_review(
        self,
        *,
        job_id: str,
        incident_id: str,
        to_status: ReviewStatus,
        reviewer: str,
        note: str,
    ) -> FinalIncidentReport:
        """Transition one report review state for a job."""

        existing = self._jobs[job_id]
        for report in existing.reports:
            if report.incident_id == incident_id:
                updated = transition_report_review(
                    report,
                    to_status=to_status,
                    reviewer=reviewer,
                    note=note,
                )
                existing.updated_at = datetime.now(UTC)
                self._jobs[job_id] = existing
                return updated
        raise KeyError(f"Report not found for incident_id={incident_id}")

    def list(self) -> list[AnalysisJobRecord]:
        """List all jobs sorted by create time."""

        return sorted(self._jobs.values(), key=lambda item: item.created_at)
