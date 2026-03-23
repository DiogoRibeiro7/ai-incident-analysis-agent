from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from incident_agent.services.pipeline import run_pipeline_from_files


def test_run_pipeline_from_files_persists_artifacts(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

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

    events = [getattr(record, "event", None) for record in caplog.records]
    assert "pipeline.run.started" in events
    assert "pipeline.stage.start" in events
    assert "pipeline.stage.completed" in events
    assert "pipeline.run.completed" in events


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
