from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from incident_agent.services.pipeline import run_pipeline_from_files


def test_run_pipeline_from_files_persists_artifacts(
    tmp_path: Path,
) -> None:
    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        artifact_root=str(tmp_path),
        bucket_size_minutes=5,
    )

    run_dir = Path(result.artifact_dir)
    assert run_dir.exists()
    assert (run_dir / "normalized" / "timeline.json").exists()
    assert (run_dir / "anomalies" / "anomalies.json").exists()
    assert (run_dir / "incidents" / "incidents.json").exists()
    assert (run_dir / "rca" / "rca_hypotheses.json").exists()
    assert (run_dir / "reports" / "final_reports.json").exists()
    assert result.final_report_count >= 1
    assert result.llm_usage.call_count >= 1
    assert result.llm_usage.total_tokens >= 0


def test_run_pipeline_from_files_degrades_when_metrics_missing(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        overrides={
            "resilience": {
                "enable_intermediate_cache": False,
                "llm_cache_dir": str(tmp_path / "llm-cache"),
                "intermediate_cache_dir": str(tmp_path / "pipeline-cache"),
                "allow_missing_metrics": True,
                "allow_missing_logs": True,
            }
        },
    )

    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path=str(tmp_path / "missing-metrics.csv"),
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
    )

    assert result.degraded is True
    assert result.warnings
    assert result.failure_summaries
    assert (Path(result.artifact_dir) / "run_summary.json").exists()


def test_run_pipeline_from_files_uses_intermediate_cache_on_repeat(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        overrides={
            "resilience": {
                "enable_intermediate_cache": True,
                "llm_cache_dir": str(tmp_path / "llm-cache"),
                "intermediate_cache_dir": str(tmp_path / "pipeline-cache"),
                "allow_missing_metrics": True,
                "allow_missing_logs": True,
            }
        },
    )

    first = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
    )
    second = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
    )

    assert first.artifact_dir != second.artifact_dir
    assert second.used_intermediate_cache is True


def test_run_pipeline_from_files_returns_partial_result_when_provider_unavailable(
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        overrides={
            "llm": {"provider": "openai"},
            "resilience": {
                "enable_intermediate_cache": False,
                "llm_cache_dir": str(tmp_path / "llm-cache"),
                "intermediate_cache_dir": str(tmp_path / "pipeline-cache"),
                "allow_missing_metrics": True,
                "allow_missing_logs": True,
            },
        },
    )

    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
    )

    assert result.degraded is True
    assert result.incident_count >= 1
    assert result.final_report_count == 0
    assert any(item.stage == "report_generation" for item in result.failure_summaries)


def test_run_pipeline_from_files_includes_citations_when_retrieval_enabled(
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        overrides={
            "knowledge": {
                "enabled": True,
                "source_paths": ["data/knowledge/runbooks", "data/knowledge/incidents"],
                "top_k": 2,
                "max_snippet_chars": 280,
            },
            "resilience": {
                "enable_intermediate_cache": False,
                "llm_cache_dir": str(tmp_path / "llm-cache"),
                "intermediate_cache_dir": str(tmp_path / "pipeline-cache"),
                "allow_missing_metrics": True,
                "allow_missing_logs": True,
            },
        },
    )

    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
    )

    assert result.final_reports
    assert any(report.citations for report in result.final_reports)
    assert any(report.claim_citations for report in result.final_reports)


def test_run_pipeline_warn_policy_keeps_reports_on_grounding_failure(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        overrides={
            "grounding": {
                "enabled": True,
                "policy": "warn",
                "minimum_support_overlap": 1.1,
            },
            "resilience": {
                "enable_intermediate_cache": False,
                "llm_cache_dir": str(tmp_path / "llm-cache"),
                "intermediate_cache_dir": str(tmp_path / "pipeline-cache"),
                "allow_missing_metrics": True,
                "allow_missing_logs": True,
            },
        },
    )

    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
    )

    assert result.final_report_count >= 1
    assert result.grounding_summaries
    assert any(item.unsupported_claims >= 1 for item in result.grounding_summaries)
    assert (Path(result.artifact_dir) / "grounding" / "grounding_summary.json").exists()


def test_run_pipeline_fail_policy_drops_failed_reports(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        overrides={
            "grounding": {
                "enabled": True,
                "policy": "fail",
                "minimum_support_overlap": 1.1,
            },
            "resilience": {
                "enable_intermediate_cache": False,
                "llm_cache_dir": str(tmp_path / "llm-cache"),
                "intermediate_cache_dir": str(tmp_path / "pipeline-cache"),
                "allow_missing_metrics": True,
                "allow_missing_logs": True,
            },
        },
    )

    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
    )

    assert result.final_report_count == 0
    assert any(item.stage == "grounding_validation" for item in result.failure_summaries)


def test_run_pipeline_from_prometheus_metrics_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from incident_agent.schemas.events import MetricPoint

    def _fake_fetch(**_kwargs: object) -> list[MetricPoint]:
        return [
            MetricPoint(
                timestamp=datetime(2026, 3, 20, 11, 15, tzinfo=UTC),
                service="checkout-service",
                metric_name="error_rate",
                value=0.24,
            ),
            MetricPoint(
                timestamp=datetime(2026, 3, 20, 11, 20, tzinfo=UTC),
                service="checkout-service",
                metric_name="request_latency_ms",
                value=1200.0,
            ),
        ]

    monkeypatch.setattr("incident_agent.services.pipeline.fetch_prometheus_metrics", _fake_fetch)
    config_path = _write_config(
        tmp_path,
        overrides={
            "resilience": {
                "enable_intermediate_cache": False,
                "llm_cache_dir": str(tmp_path / "llm-cache"),
                "intermediate_cache_dir": str(tmp_path / "pipeline-cache"),
                "allow_missing_metrics": True,
                "allow_missing_logs": True,
            },
            "connectors": {
                "prometheus": {
                    "enabled": True,
                    "base_url": "http://example-prometheus:9090",
                    "metric_queries": {"error_rate": "up", "request_latency_ms": "up"},
                }
            },
        },
    )

    result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="unused.csv",
        config_path=str(config_path),
        artifact_root=str(tmp_path / "runs"),
        bucket_size_minutes=5,
        metrics_source="prometheus",
    )

    assert result.normalized_event_count >= 6
    assert result.failure_summaries == []


def _write_config(tmp_path: Path, overrides: dict[str, object]) -> Path:
    base = yaml.safe_load(Path("configs/default.yaml").read_text(encoding="utf-8"))
    assert isinstance(base, dict)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged = dict(base[key])
            merged.update(value)
            base[key] = merged
        else:
            base[key] = value
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")
    return path
