from __future__ import annotations

from pathlib import Path

from incident_agent.ingestion.logs import ingest_logs


def test_ingest_logs_csv_with_duplicates_and_invalid_rows(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.csv"
    log_path.write_text(
        "\n".join(
            [
                "timestamp,service,severity,message,trace_id,metadata",
                '2026-03-20T11:00:00Z,api-service,error,Failure one,abc-1,"{""env"":""prod""}"',
                '2026-03-20T11:00:00Z,api-service,error,Failure one,abc-1,"{""env"":""prod""}"',
                "2026-03-20T11:01:00Z,,ERROR,Missing service,abc-2,{}",
                "2026-03-20T11:02:00,api-service,WARN,Naive timestamp row,abc-3,{}",
                "2026-03-20T11:03:00Z,api-service,BOOM,Bad severity,abc-4,{}",
            ]
        ),
        encoding="utf-8",
    )

    result = ingest_logs(log_path)

    assert len(result.records) == 2
    assert result.report.total_rows == 5
    assert result.report.valid_rows == 2
    assert result.report.invalid_rows == 2
    assert result.report.dropped_duplicates == 1
    assert result.report.parse_warnings == 1
    assert result.records[0].severity == "ERROR"


def test_ingest_logs_jsonl_handles_malformed_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    log_path.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-03-20T11:00:00Z","service":"api","severity":"ERROR","message":"boom"}',
                "{not-json",
                '{"timestamp":"2026-03-20T11:01:00Z","service":"api","severity":"WARN","message":"warn"}',
            ]
        ),
        encoding="utf-8",
    )

    result = ingest_logs(log_path)

    assert len(result.records) == 2
    assert result.report.total_rows == 3
    assert result.report.invalid_rows == 1
