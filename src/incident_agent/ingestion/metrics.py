"""Metric ingestion with validation and normalization."""

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
from incident_agent.schemas.events import MetricPoint


def ingest_metrics(path: str | Path) -> IngestionResult[MetricPoint]:
    """Ingest metrics from CSV, JSON, or JSONL and return normalized records."""

    source = Path(path)
    data_format = detect_format(source)
    if data_format not in {IngestionFormat.CSV, IngestionFormat.JSON, IngestionFormat.JSONL}:
        raise ValueError("Metrics ingestion supports only .csv, .json, or .jsonl files.")

    report = DataQualityReport()
    records: list[MetricPoint] = []
    seen_keys: set[str] = set()

    for row_number, payload in _iter_metric_payloads(source, data_format):
        report.total_rows += 1
        point = _normalize_metric_payload(payload, report=report, row_number=row_number)
        if point is None:
            report.invalid_rows += 1
            continue

        dedupe_key = json.dumps(point.model_dump(mode="json"), sort_keys=True)
        if dedupe_key in seen_keys:
            report.dropped_duplicates += 1
            continue

        seen_keys.add(dedupe_key)
        report.valid_rows += 1
        records.append(point)

    return IngestionResult(records=records, report=report)


def _iter_metric_payloads(
    path: Path, data_format: IngestionFormat
) -> Iterator[tuple[int, dict[str, object]]]:
    if data_format is IngestionFormat.CSV:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                yield row_number, {str(key): value for key, value in row.items() if key is not None}
        return

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

    with path.open("r", encoding="utf-8") as handle:
        try:
            payload = json.load(handle)
        except json.JSONDecodeError as error:
            yield 1, {"_error": f"Malformed JSON: {error.msg}"}
            return

    if isinstance(payload, list):
        for row_number, row in enumerate(payload, start=1):
            if isinstance(row, dict):
                yield row_number, row
            else:
                yield row_number, {"_error": "Expected JSON object in list."}
        return

    if isinstance(payload, dict):
        rows = payload.get("metrics")
        if isinstance(rows, list):
            for row_number, row in enumerate(rows, start=1):
                if isinstance(row, dict):
                    yield row_number, row
                else:
                    yield row_number, {"_error": "Expected JSON object in 'metrics' list."}
            return

    yield 1, {"_error": "Expected JSON array or object with 'metrics' array."}


def _normalize_metric_payload(
    payload: dict[str, object], *, report: DataQualityReport, row_number: int
) -> MetricPoint | None:
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

    metric_name = _parse_required_string(payload.get("metric_name"))
    if metric_name is None:
        report.add_error(f"Row {row_number}: missing metric_name.")
        return None

    value = _parse_float(payload.get("value"))
    if value is None:
        report.add_error(f"Row {row_number}: invalid metric value '{payload.get('value')}'.")
        return None

    unit = _parse_optional_string(payload.get("unit"))
    tags = _parse_tags(payload.get("tags"), report=report, row_number=row_number)

    return MetricPoint(
        timestamp=timestamp,
        service=service,
        metric_name=metric_name,
        value=value,
        unit=unit,
        tags=tags,
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


def _parse_float(value: object) -> float | None:
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        try:
            return float(trimmed)
        except ValueError:
            return None
    return None


def _parse_tags(value: object, *, report: DataQualityReport, row_number: int) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(tag_value) for key, tag_value in value.items()}
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return {}
        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError:
            report.add_warning(f"Row {row_number}: tags is not valid JSON; ignoring.")
            return {}
        if isinstance(decoded, dict):
            return {str(key): str(tag_value) for key, tag_value in decoded.items()}
        report.add_warning(f"Row {row_number}: tags JSON should be an object; ignoring.")
        return {}

    report.add_warning(f"Row {row_number}: tags has unsupported type '{type(value).__name__}'.")
    return {}
