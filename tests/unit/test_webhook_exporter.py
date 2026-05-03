from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from incident_agent.export.webhook import (
    WebhookExportConfig,
    WebhookExportError,
    export_report_via_webhook,
)
from incident_agent.schemas.final_report import FinalIncidentReport


def _approved_report() -> FinalIncidentReport:
    return FinalIncidentReport(
        incident_id="inc-1",
        incident_summary="summary",
        root_cause_explanation="cause",
        executive_summary="exec",
        engineering_handoff="handoff",
        review_status="approved",
    )


def test_webhook_export_retries_transient_and_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    responses = [
        httpx.Response(status_code=500, json={"error": "retry"}),
        httpx.Response(status_code=200, json={"payload_id": "ext-123"}),
    ]

    class _FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return responses.pop(0)

    monkeypatch.setattr("incident_agent.export.webhook.httpx.Client", _FakeClient)
    record = export_report_via_webhook(
        report=_approved_report(),
        destination_url="https://example.test/webhook",
        audit_log_path=tmp_path / "audit.jsonl",
        config=WebhookExportConfig(max_retries=2, retry_backoff_seconds=0.0),
    )
    assert record.status == "delivered"
    assert record.attempts == 2
    assert record.payload_id == "ext-123"


def test_webhook_export_records_permanent_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(status_code=400, json={"error": "bad request"})

    monkeypatch.setattr("incident_agent.export.webhook.httpx.Client", _FakeClient)
    audit_path = tmp_path / "audit.jsonl"
    with pytest.raises(WebhookExportError):
        export_report_via_webhook(
            report=_approved_report(),
            destination_url="https://example.test/webhook",
            audit_log_path=audit_path,
            config=WebhookExportConfig(max_retries=1, retry_backoff_seconds=0.0),
        )
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert lines
    payload = json.loads(lines[-1])
    assert payload["status"] == "failed"
