"""Log ingestion with validation and normalization."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path

from incident_agent.ingestion.common import (
    DataQualityReport,
    IngestionFormat,
    IngestionResult,
    detect_format,
    parse_timestamp_to_utc,
)
from incident_agent.schemas.events import LogEvent

VALID_SEVERITIES = {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}


def ingest_logs(path: str | Path) -> IngestionResult[LogEvent]:
    """Ingest logs from CSV or JSONL and return normalized records."""

    source = Path(path)
    data_format = detect_format(source)
    if data_format not in {IngestionFormat.JSONL, IngestionFormat.CSV}:
        raise ValueError("Logs ingestion supports only .jsonl or .csv files.")

    report = DataQualityReport()
    records: list[LogEvent] = []
    seen_keys: set[str] = set()

    for row_number, payload in _iter_log_payloads(source, data_format):
        report.total_rows += 1
        event = _normalize_log_payload(payload, report=report, row_number=row_number)
        if event is None:
            report.invalid_rows += 1
            continue

        dedupe_key = json.dumps(event.model_dump(mode="json"), sort_keys=True)
        if dedupe_key in seen_keys:
            report.dropped_duplicates += 1
            continue

        seen_keys.add(dedupe_key)
        report.valid_rows += 1
        records.append(event)

    return IngestionResult(records=records, report=report)


def _iter_log_payloads(
    path: Path, data_format: IngestionFormat
) -> Iterator[tuple[int, dict[str, object]]]:
    if data_format is IngestionFormat.JSONL:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    yield line_number, {"_error": f"Malformed JSON: {error.msg}"}
                    continue
                if not isinstance(payload, dict):
                    yield line_number, {"_error": "Expected JSON object per line."}
                    continue
                yield line_number, payload
        return

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            yield row_number, {str(key): value for key, value in row.items() if key is not None}


def _normalize_log_payload(
    payload: dict[str, object], *, report: DataQualityReport, row_number: int
) -> LogEvent | None:
    row_error = payload.get("_error")
    if isinstance(row_error, str):
        report.add_error(f"Row {row_number}: {row_error}")
        return None

    timestamp = parse_timestamp_to_utc(payload.get("timestamp"), report, row_number=row_number)
    if timestamp is None:
        return None

    service = _parse_required_string(payload.get("service"))
    if service is None:
        report.add_error(f"Row {row_number}: missing service.")
        return None

    severity_raw = _parse_required_string(payload.get("severity"))
    if severity_raw is None:
        report.add_error(f"Row {row_number}: missing severity.")
        return None
    severity = severity_raw.upper()
    if severity not in VALID_SEVERITIES:
        report.add_error(f"Row {row_number}: invalid severity '{severity_raw}'.")
        return None

    message = _parse_required_string(payload.get("message"))
    if message is None:
        report.add_error(f"Row {row_number}: missing message.")
        return None

    trace_id = _parse_optional_string(payload.get("trace_id"))
    metadata = _parse_metadata(payload, report=report, row_number=row_number)

    return LogEvent(
        timestamp=timestamp,
        service=service,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        trace_id=trace_id,
        metadata=metadata,
    )


def _parse_required_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _parse_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _parse_metadata(
    payload: dict[str, object], *, report: DataQualityReport, row_number: int
) -> dict[str, str | int | float | bool | None]:
    raw_metadata = payload.get("metadata")
    metadata: dict[str, str | int | float | bool | None] = {}

    if raw_metadata is None:
        pass
    elif isinstance(raw_metadata, dict):
        for key, value in raw_metadata.items():
            if isinstance(key, str):
                metadata[key] = _coerce_simple_value(value)
    elif isinstance(raw_metadata, str):
        candidate = raw_metadata.strip()
        if candidate:
            try:
                decoded = json.loads(candidate)
            except json.JSONDecodeError:
                report.add_warning(
                    f"Row {row_number}: metadata is not valid JSON; keeping as raw string."
                )
                metadata["raw_metadata"] = candidate
            else:
                if isinstance(decoded, dict):
                    for key, value in decoded.items():
                        if isinstance(key, str):
                            metadata[key] = _coerce_simple_value(value)
                else:
                    report.add_warning(
                        f"Row {row_number}: metadata JSON should be an object; keeping raw value."
                    )
                    metadata["raw_metadata"] = candidate
    else:
        report.add_warning(
            f"Row {row_number}: metadata has unsupported type '{type(raw_metadata).__name__}'."
        )

    reserved = {"timestamp", "service", "severity", "message", "trace_id", "metadata"}
    for key, value in payload.items():
        if key not in reserved and value not in (None, ""):
            metadata[key] = _coerce_simple_value(value)
    return metadata


def _coerce_simple_value(value: object) -> str | int | float | bool | None:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)
