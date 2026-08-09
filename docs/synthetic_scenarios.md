# Synthetic Scenarios

Synthetic scenarios provide reproducible logs, metrics, and planted metadata for demos and evaluation.

## Supported scenario types

- `healthy_stable`
- `healthy_noisy`
- `normal_traffic_variability`
- `transient_latency_spike`
- `latency_degradation`
- `gradual_latency_drift`
- `error_burst`
- `persistent_error_rate`
- `error_logs_only`
- `metrics_only_degradation`
- `cpu_saturation`
- `memory_saturation`
- `resource_anomaly_no_impact`
- `dependency_cascade`
- `upstream_root_cause`
- `downstream_symptoms`
- `unrelated_simultaneous`
- `traffic_drop`
- `traffic_disappearance`
- `isolated_low_volume_bucket`
- `resource_exhaustion`
- `partial_outage`
- `heartbeat_loss`
- `temporary_unavailability`
- `missing_observability`
- `ambiguous_root_causes`
- `contradictory_telemetry`
- `insufficient_evidence`
- `missing_logs`
- `missing_metrics`
- `sparse_observations`

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
They can also define labels used by the evaluation harness, including
`incident_expected`, `expected_root_cause`, `allowed_root_causes`,
`expected_impacted_services`, `expected_anomaly_types`, `expected_min_incidents`,
and `expected_max_incidents`.

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
