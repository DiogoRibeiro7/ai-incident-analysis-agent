"""Schemas for deterministic demo execution."""

from __future__ import annotations

from pydantic import BaseModel


class DemoRunResult(BaseModel):
    """Summary of one recruiter-facing demo run."""

    demo_dir: str
    artifact_dir: str
    markdown_report_path: str | None = None
    html_report_path: str | None = None
    anomaly_artifact_path: str
    incident_artifact_path: str
    rca_artifact_path: str
    run_summary_path: str
