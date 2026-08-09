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

_PUBLIC_TEST_HOST = "93.184.216.34"


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
        destination_url=f"https://{_PUBLIC_TEST_HOST}/webhook",
        audit_log_path=tmp_path / "audit.jsonl",
        config=WebhookExportConfig(
            max_retries=2,
            retry_backoff_seconds=0.0,
            allowed_urls=[f"https://{_PUBLIC_TEST_HOST}/webhook"],
        ),
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
            destination_url=f"https://{_PUBLIC_TEST_HOST}/webhook",
            audit_log_path=audit_path,
            config=WebhookExportConfig(
                max_retries=1,
                retry_backoff_seconds=0.0,
                allowed_urls=[f"https://{_PUBLIC_TEST_HOST}/webhook"],
            ),
        )
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert lines
    payload = json.loads(lines[-1])
    assert payload["status"] == "failed"


def test_webhook_export_blocks_redirect_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _RedirectClient:
        def __init__(self, *_args: object, **kwargs: object) -> None:
            assert kwargs["follow_redirects"] is False

        def __enter__(self) -> _RedirectClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(status_code=302, headers={"location": "http://127.0.0.1"})

    monkeypatch.setattr("incident_agent.export.webhook.httpx.Client", _RedirectClient)

    with pytest.raises(WebhookExportError, match="redirect blocked"):
        export_report_via_webhook(
            report=_approved_report(),
            destination_url=f"https://{_PUBLIC_TEST_HOST}/webhook",
            audit_log_path=tmp_path / "audit.jsonl",
            config=WebhookExportConfig(
                max_retries=0,
                retry_backoff_seconds=0.0,
                allowed_urls=[f"https://{_PUBLIC_TEST_HOST}/webhook"],
            ),
        )


def test_webhook_export_rejects_unallowlisted_host(tmp_path: Path) -> None:
    with pytest.raises(WebhookExportError, match="allowlist"):
        export_report_via_webhook(
            report=_approved_report(),
            destination_url=f"https://{_PUBLIC_TEST_HOST}/webhook",
            audit_log_path=tmp_path / "audit.jsonl",
            config=WebhookExportConfig(allowed_urls=["https://hooks.example.com/webhook"]),
        )
