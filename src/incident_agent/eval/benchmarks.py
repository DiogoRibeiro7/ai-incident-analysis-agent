"""Benchmark scenario loading."""

from __future__ import annotations

import json
from pathlib import Path

from incident_agent.schemas.eval import BenchmarkScenario


def load_benchmark_scenarios(path: str | Path) -> list[BenchmarkScenario]:
    """Load benchmark scenarios from a JSON file."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Benchmark file must contain a JSON array.")
    scenarios = [BenchmarkScenario.model_validate(item) for item in raw]
    return scenarios
