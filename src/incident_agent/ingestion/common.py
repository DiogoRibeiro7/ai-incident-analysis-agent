"""Shared ingestion models and helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class IngestionFormat(StrEnum):
    """Supported on-disk record formats."""

    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"


class DataQualityReport(BaseModel):
    """Quality counters produced by ingestion runs."""

    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    dropped_duplicates: int = 0
    parse_warnings: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def add_warning(self, message: str) -> None:
        """Append a parse warning and increment the counter."""

        self.parse_warnings += 1
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Append a validation error."""

        self.errors.append(message)


class IngestionResult[TRecord](BaseModel):
    """Result bundle with normalized records and quality metadata."""

    records: list[TRecord]
    report: DataQualityReport


def detect_format(path: Path) -> IngestionFormat:
    """Detect ingestion format from file extension."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return IngestionFormat.CSV
    if suffix == ".json":
        return IngestionFormat.JSON
    if suffix == ".jsonl":
        return IngestionFormat.JSONL
    raise ValueError(f"Unsupported file extension '{suffix}' for '{path}'.")


def parse_timestamp_to_utc(
    value: object,
    report: DataQualityReport,
    *,
    row_number: int,
    field_name: str = "timestamp",
) -> datetime | None:
    """Parse a timestamp value and normalize it to timezone-aware UTC."""

    if value is None:
        report.add_error(f"Row {row_number}: missing {field_name}.")
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            report.add_error(f"Row {row_number}: missing {field_name}.")
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            report.add_error(f"Row {row_number}: invalid {field_name} '{raw}'. Expected ISO 8601.")
            return None
    else:
        report.add_error(f"Row {row_number}: invalid {field_name} type '{type(value).__name__}'.")
        return None

    if parsed.tzinfo is None:
        report.add_warning(f"Row {row_number}: naive {field_name} assumed to be UTC.")
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)
