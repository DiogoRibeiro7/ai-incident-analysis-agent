from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from incident_agent.cli import app
from incident_agent.eval.benchmarks import load_benchmark_scenarios
from incident_agent.eval.runner import run_evaluation
from incident_agent.schemas.eval import SyntheticScenarioGeneratorConfig
from incident_agent.synthetic.generator import generate_benchmark_scenario


def test_generate_benchmark_scenario_writes_logs_metrics_and_metadata(tmp_path: Path) -> None:
    scenario = generate_benchmark_scenario(
        scenario_id="synthetic-resource-exhaustion",
        description="Synthetic resource exhaustion benchmark.",
        config=SyntheticScenarioGeneratorConfig(
            scenario_type="resource_exhaustion",
            root_cause_service="api-service",
            impacted_services=["api-service", "checkout-service"],
            seed=31,
        ),
        output_root=tmp_path,
    )

    assert Path(scenario.logs_path).exists()
    assert Path(scenario.metrics_path).exists()
    assert Path(scenario.metadata_path or "").exists()

    metadata = json.loads(Path(scenario.metadata_path or "").read_text(encoding="utf-8"))
    assert metadata["root_cause_service"] == "api-service"
    assert metadata["scenario_type"] == "resource_exhaustion"


def test_load_benchmark_scenarios_generates_synthetic_assets(tmp_path: Path) -> None:
    benchmark_path = tmp_path / "synthetic.json"
    benchmark_path.write_text(
        json.dumps(
            [
                {
                    "scenario_id": "generated-error-burst",
                    "description": "Generated error burst scenario.",
                    "logs_path": "",
                    "metrics_path": "",
                    "generator": {
                        "scenario_type": "error_burst",
                        "root_cause_service": "checkout-service",
                        "impacted_services": ["checkout-service"],
                        "seed": 5,
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    scenarios = load_benchmark_scenarios(benchmark_path)

    assert len(scenarios) == 1
    assert Path(scenarios[0].logs_path).exists()
    assert Path(scenarios[0].metrics_path).exists()


def test_run_evaluation_with_synthetic_benchmark_file(tmp_path: Path) -> None:
    benchmark_copy = tmp_path / "synthetic_scenarios.json"
    benchmark_copy.write_text(
        Path("eval/benchmarks/synthetic_scenarios.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result = run_evaluation(
        benchmark_path=str(benchmark_copy),
        artifact_root=str(tmp_path),
        include_real_llm=False,
    )

    assert result.records
    assert result.summaries
    generated_root = tmp_path / "generated"
    assert generated_root.exists()


def test_generate_scenario_cli_outputs_generated_paths(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "generate-scenario",
            "--scenario-id",
            "cli-generated-outage",
            "--scenario-type",
            "partial_outage",
            "--root-cause-service",
            "gateway-service",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "metadata_path" in result.stdout
