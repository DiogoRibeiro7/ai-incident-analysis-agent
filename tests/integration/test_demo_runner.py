from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from incident_agent.cli import app
from incident_agent.services.demo import run_demo


def test_run_demo_service_writes_stable_demo_artifacts(tmp_path: Path) -> None:
    result = run_demo(output_root=str(tmp_path / "demo"))

    demo_dir = Path(result.demo_dir)
    assert demo_dir.exists()
    assert Path(result.anomaly_artifact_path).exists()
    assert Path(result.incident_artifact_path).exists()
    assert Path(result.rca_artifact_path).exists()
    assert Path(result.run_summary_path).exists()
    assert Path(result.markdown_report_path or "").exists()
    assert Path(result.html_report_path or "").exists()
    assert (demo_dir / "demo_manifest.json").exists()


def test_run_demo_cli_outputs_demo_manifest(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-demo",
            "--output-dir",
            str(tmp_path / "demo"),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert Path(payload["demo_dir"]).exists()
    assert Path(payload["markdown_report_path"]).exists()
    assert Path(payload["html_report_path"]).exists()
