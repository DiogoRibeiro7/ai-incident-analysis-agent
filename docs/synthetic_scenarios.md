# Synthetic Scenarios

Synthetic scenarios provide reproducible logs, metrics, and planted metadata for demos and evaluation.

## Supported scenario types

- `latency_degradation`
- `error_burst`
- `dependency_cascade`
- `traffic_drop`
- `resource_exhaustion`
- `partial_outage`

## CLI

```bash
poetry run incident-agent generate-scenario \
  --scenario-id demo-latency \
  --scenario-type latency_degradation \
  --root-cause-service checkout-service
```

The command writes:
- `logs.csv`
- `metrics.csv`
- `metadata.json`

## Evaluation integration

Benchmark files can include a `generator` object instead of concrete log and metric paths.

Example:

```json
{
  "scenario_id": "synthetic_latency_degradation",
  "description": "Generated latency degradation scenario",
  "logs_path": "",
  "metrics_path": "",
  "generator": {
    "scenario_type": "latency_degradation",
    "root_cause_service": "checkout-service",
    "impacted_services": ["checkout-service"]
  }
}
```

When loaded by the evaluation harness, generated datasets are written under a sibling `generated/` directory next to the benchmark file.
