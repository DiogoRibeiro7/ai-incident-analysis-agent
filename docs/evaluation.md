# Evaluation Harness

## Goal

Measure incident analysis quality across benchmark scenarios and compare output modes:
- `heuristic-only`
- `mock-llm`
- optional `real-llm`

## Components

- Runner: `src/incident_agent/eval/runner.py`
- Benchmark loader: `src/incident_agent/eval/benchmarks.py`
- Schemas: `src/incident_agent/schemas/eval.py`
- Benchmarks: `eval/benchmarks/scenarios.json`
- Synthetic benchmarks: `eval/benchmarks/synthetic_scenarios.json`

## Metrics

Per scenario and mode, the harness records:
- root-cause correctness
- impacted service correctness
- factual grounding
- hallucination rate
- report completeness
- latency (seconds)
- token usage (when available; currently `null`)

## Artifacts

Each evaluation run writes:
- `records.json` (machine-readable per-run records)
- `summary.json` (machine-readable per-mode aggregates)
- `summary.md` (human-readable summary table)

Default output root:
- `artifacts/eval/<run_id>/...`

## CLI usage

```bash
poetry run incident-agent run-eval \
  --benchmark-path eval/benchmarks/scenarios.json \
  --artifact-root artifacts/eval
```

Include real LLM mode:

```bash
poetry run incident-agent run-eval \
  --include-real-llm
```

`real-llm` requires `llm.provider` support and credentials in config/env.

## Synthetic generation

Benchmark files may include `generator` definitions instead of concrete input files.

When present, the benchmark loader generates:
- `logs.csv`
- `metrics.csv`
- `metadata.json`

Generated files are written under a sibling `generated/` directory next to the benchmark file.

See `docs/synthetic_scenarios.md` for supported scenario types and the CLI workflow.
