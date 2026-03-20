from __future__ import annotations

from incident_agent.services.analyze import analyze_from_files


def test_analyze_from_files_returns_reports() -> None:
    reports = analyze_from_files(
        log_path="data/sample/logs.jsonl",
        metric_path="data/sample/metrics.jsonl",
    )

    assert reports
    assert reports[0].title == "Mock incident report"
