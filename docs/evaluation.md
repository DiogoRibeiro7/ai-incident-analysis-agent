# Evaluation Harness

## Goal

Measure incident analysis quality across benchmark scenarios and compare output modes:
- `heuristic-only`
- `mock-llm-no-retrieval`
- `mock-llm-retrieval`
- optional `real-llm-no-retrieval`
- optional `real-llm-retrieval`

## Components

- Runner: `src/incident_agent/eval/runner.py`
- Benchmark loader: `src/incident_agent/eval/benchmarks.py`
- Schemas: `src/incident_agent/schemas/eval.py`
- Benchmarks: `eval/benchmarks/scenarios.json`
- Synthetic benchmarks: `eval/benchmarks/synthetic_scenarios.json`
- Golden baseline summary: `eval/golden/baseline_summary.json`
- Golden report property fixture: `eval/golden/report_properties.json`

## Metrics

Per scenario and mode, the harness records:
- root-cause correctness
- impacted service correctness
- service entity precision
- unexpected service mention rate
- claim citation coverage
- factual claim counts by validation status
- factual claim support, unsupported, and contradictory rates
- report completeness
- latency (seconds)
- token usage
- estimated cost (USD)

Claim-grounding rates are derived from grounding validation over generated report
prose. When a report has zero factual claims, claim support, unsupported, and
contradictory rates are recorded as `0.0` so unevaluable output is not silently
treated as perfectly grounded.

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

## Regression Comparison

Compare a candidate eval run against the checked-in baseline:

```bash
poetry run incident-agent compare-eval \
  --baseline-summary-path eval/golden/baseline_summary.json \
  --candidate-summary-path artifacts/eval/<run_id>/summary.json \
  --output-dir artifacts/eval/compare
```

Outputs:
- `eval_comparison.json`
- `eval_comparison.md`

The command exits with code `1` when configured regression thresholds are exceeded.
It also fails when candidate summaries omit a baseline mode or include a mode that is
not present in the baseline. Mode names are validated against the canonical set
listed above.

## Synthetic generation

Benchmark files may include `generator` definitions instead of concrete input files.

When present, the benchmark loader generates:
- `logs.csv`
- `metrics.csv`
- `metadata.json`

Generated files are written under a sibling `generated/` directory next to the benchmark file.

See `docs/synthetic_scenarios.md` for supported scenario types and the CLI workflow.
