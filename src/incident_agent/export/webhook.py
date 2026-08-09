"""Generic webhook exporter for approved incident reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from incident_agent.schemas.final_report import FinalIncidentReport
from incident_agent.utils.security import OutboundUrlPolicyError, validate_outbound_url


class WebhookExportConfig(BaseModel):
    """Runtime options for webhook delivery."""

    timeout_seconds: float = 10.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    allowed_urls: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=list)
    allow_http: bool = False
    allow_private_networks: bool = False


class WebhookDeliveryRecord(BaseModel):
    """Audit record for one outbound webhook delivery."""

    delivery_id: str
    incident_id: str
    destination_url: str
    status: str
    attempts: int
    payload_id: str | None = None
    error: str | None = None
    delivered_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebhookExportError(RuntimeError):
    """Raised when webhook export fails."""


def export_report_via_webhook(
    *,
    report: FinalIncidentReport,
    destination_url: str,
    audit_log_path: str | Path,
    config: WebhookExportConfig | None = None,
) -> WebhookDeliveryRecord:
    """Export one approved report to webhook with retries and audit logging."""

    if report.review_status != "approved":
        raise WebhookExportError("Only approved reports can be exported.")
    effective = config or WebhookExportConfig()
    safe_destination_url = _allowed_webhook_destination(
        requested_url=destination_url,
        allowed_urls=effective.allowed_urls,
    )
    allowed_hosts = effective.allowed_hosts or [_hostname_for_allowed_url(safe_destination_url)]
    try:
        validated_url = validate_outbound_url(
            safe_destination_url,
            allowed_hosts=allowed_hosts,
            allowed_schemes={"http", "https"} if effective.allow_http else {"https"},
            allow_private_networks=effective.allow_private_networks,
        )
    except OutboundUrlPolicyError as error:
        raise WebhookExportError(str(error)) from error
    delivery_id = f"delivery-{uuid4().hex[:12]}"
    payload = {
        "delivery_id": delivery_id,
        "sent_at": datetime.now(UTC).isoformat(),
        "report": report.model_dump(mode="json"),
    }
    attempts = 0
    last_error: str | None = None
    payload_id: str | None = None

    for attempt in range(1, effective.max_retries + 2):
        attempts = attempt
        try:
            with httpx.Client(timeout=effective.timeout_seconds, follow_redirects=False) as client:
                response = client.post(validated_url, json=payload)
            if 300 <= response.status_code < 400:
                last_error = f"Webhook redirect blocked: status {response.status_code}."
                break
            if response.status_code >= 500:
                last_error = f"Webhook temporary server error: status {response.status_code}."
            elif response.status_code >= 400:
                last_error = f"Webhook permanent failure: status {response.status_code}."
                break
            else:
                payload_id = _extract_payload_id(response)
                record = WebhookDeliveryRecord(
                    delivery_id=delivery_id,
                    incident_id=report.incident_id,
                    destination_url=destination_url,
                    status="delivered",
                    attempts=attempts,
                    payload_id=payload_id,
                    delivered_at=datetime.now(UTC),
                )
                _append_delivery_audit(path=Path(audit_log_path), record=record)
                return record
        except httpx.HTTPError as error:
            last_error = f"Webhook network error: {error}"

        if attempt <= effective.max_retries:
            sleep(effective.retry_backoff_seconds * attempt)

    failed = WebhookDeliveryRecord(
        delivery_id=delivery_id,
        incident_id=report.incident_id,
        destination_url=destination_url,
        status="failed",
        attempts=attempts,
        payload_id=payload_id,
        error=last_error or "Webhook delivery failed.",
    )
    _append_delivery_audit(path=Path(audit_log_path), record=failed)
    raise WebhookExportError(failed.error or "Webhook delivery failed.")


def _extract_payload_id(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        value = payload.get("payload_id") or payload.get("id")
        if isinstance(value, str):
            return value
    return None


def _allowed_webhook_destination(*, requested_url: str, allowed_urls: list[str]) -> str:
    requested = requested_url.strip()
    for allowed_url in allowed_urls:
        normalized = allowed_url.strip()
        if requested == normalized:
            return normalized
    raise WebhookExportError("Webhook destination URL is not in the allowlist.")


def _hostname_for_allowed_url(url: str) -> str:
    parsed = httpx.URL(url)
    if parsed.host is None:
        raise WebhookExportError("Webhook destination URL must include a hostname.")
    return parsed.host


def _append_delivery_audit(*, path: Path, record: WebhookDeliveryRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(mode="json")))
        handle.write("\n")
