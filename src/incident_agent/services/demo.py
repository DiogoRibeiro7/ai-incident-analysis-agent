"""Deterministic demo workflow for recruiters and portfolio readers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from incident_agent.export.serializers import serialize_report
from incident_agent.schemas.demo import DemoRunResult
from incident_agent.services.pipeline import run_pipeline_from_files


def run_demo(
    *,
    output_root: str = "artifacts/demo/portfolio-demo",
    config_path: str = "configs/default.yaml",
    include_html: bool = True,
) -> DemoRunResult:
    """Run a deterministic end-to-end demo using bundled incident sample data."""

    demo_dir = Path(output_root)
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir(parents=True, exist_ok=True)

    pipeline_result = run_pipeline_from_files(
        log_path="data/sample/incident/anomaly_logs.csv",
        metric_path="data/sample/incident/anomaly_metrics.csv",
        config_path=config_path,
        artifact_root=str(demo_dir / "pipeline-runs"),
        bucket_size_minutes=5,
    )

    run_artifacts = Path(pipeline_result.artifact_dir)
    stable_artifact_dir = demo_dir / "artifacts"
    shutil.copytree(run_artifacts, stable_artifact_dir)

    markdown_report_path: Path | None = None
    html_report_path: Path | None = None
    if pipeline_result.final_reports:
        report = pipeline_result.final_reports[0]
        markdown_report_path = demo_dir / "incident_report.md"
        markdown_report_path.write_text(
            serialize_report(report, output_format="md"),
            encoding="utf-8",
        )
        if include_html:
            html_report_path = demo_dir / "incident_report.html"
            html_report_path.write_text(
                serialize_report(report, output_format="html"),
                encoding="utf-8",
            )

    result = DemoRunResult(
        demo_dir=str(demo_dir),
        artifact_dir=str(stable_artifact_dir),
        markdown_report_path=str(markdown_report_path) if markdown_report_path else None,
        html_report_path=str(html_report_path) if html_report_path else None,
        anomaly_artifact_path=str(stable_artifact_dir / "anomalies" / "anomalies.json"),
        incident_artifact_path=str(stable_artifact_dir / "incidents" / "incidents.json"),
        rca_artifact_path=str(stable_artifact_dir / "rca" / "rca_hypotheses.json"),
        run_summary_path=str(stable_artifact_dir / "run_summary.json"),
    )
    (demo_dir / "demo_manifest.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    _write_demo_readme(demo_dir=demo_dir, result=result)
    return result


def _write_demo_readme(*, demo_dir: Path, result: DemoRunResult) -> None:
    lines = [
        "# Demo Output",
        "",
        "This directory contains a deterministic end-to-end demo run.",
        "",
        "Artifacts:",
        f"- anomalies: `{Path(result.anomaly_artifact_path).name}`",
        f"- incidents: `{Path(result.incident_artifact_path).name}`",
        f"- RCA: `{Path(result.rca_artifact_path).name}`",
        f"- run summary: `{Path(result.run_summary_path).name}`",
    ]
    if result.markdown_report_path is not None:
        lines.append(f"- markdown report: `{Path(result.markdown_report_path).name}`")
    if result.html_report_path is not None:
        lines.append(f"- html report: `{Path(result.html_report_path).name}`")
    (demo_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
