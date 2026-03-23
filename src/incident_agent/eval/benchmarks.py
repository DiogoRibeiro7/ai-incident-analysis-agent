"""Benchmark scenario loading."""

from __future__ import annotations

import json
from pathlib import Path

from incident_agent.schemas.eval import BenchmarkScenario
from incident_agent.synthetic.generator import generate_benchmark_scenario


def load_benchmark_scenarios(path: str | Path) -> list[BenchmarkScenario]:
    """Load benchmark scenarios from a JSON file."""

    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Benchmark file must contain a JSON array.")
    scenarios: list[BenchmarkScenario] = []
    generated_root = source.parent / "generated"
    for item in raw:
        scenario = BenchmarkScenario.model_validate(item)
        if scenario.generator is not None:
            scenario = generate_benchmark_scenario(
                scenario_id=scenario.scenario_id,
                description=scenario.description,
                config=scenario.generator,
                output_root=generated_root,
            )
        scenarios.append(scenario)
    return scenarios
