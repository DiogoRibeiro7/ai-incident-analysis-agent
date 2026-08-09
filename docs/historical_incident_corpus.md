# Historical Incident Corpus

## Goal

Provide structured prior-incident records for retrieval experiments.

## Supported Formats

- `.json` with root key `historical_incidents` (list of records)
- `.json` as a plain list of incident records
- `.jsonl` with one incident record per line

## Recommended Record Shape

```json
{
  "incident_id": "hist-2026-03-01-01",
  "occurred_at": "2026-03-01T11:20:00Z",
  "primary_service": "checkout-service",
  "impacted_services": ["api-service", "cart-service"],
  "anomaly_types": ["latency_spike", "error_rate_spike"],
  "incident_summary": "Checkout latency and 5xx rate rose after deploy.",
  "root_cause": "Connection pool saturation in checkout-service",
  "resolution": "Rollback deployment and scale pool limits",
  "tags": ["payments", "latency", "deploy"]
}
```

## Usage

Point retrieval at one or more corpus files/directories:

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --retrieval-enabled \
  --knowledge-source-paths data/knowledge/runbooks \
  --knowledge-source-paths data/knowledge/incidents \
  --knowledge-source-paths data/knowledge/historical_incidents.json
```

## Notes

- Metadata fields are preserved in normalized retrieval chunks for filtering/ranking experiments.
- Corpus paths must resolve under `security.allowed_read_paths`; traversal and
  symlink escapes are rejected before retrieval reads files.
- Records missing meaningful incident text are ignored.
- Non-incident JSON entries still load as generic JSON chunks for backward compatibility.
