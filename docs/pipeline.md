# End-to-End Pipeline

## Goal

Run one command that executes:
- ingestion
- normalization
- anomaly detection
- correlation
- RCA
- final report generation
- optional retrieval context enrichment with citations

and persists each stage output as inspectable artifacts.

## Orchestrator

Implementation:
- `src/incident_agent/services/pipeline.py`

Result model:
- `src/incident_agent/schemas/pipeline.py`
- `PipelineRunResult`

## CLI usage

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --artifact-root artifacts/pipeline \
  --bucket-size-minutes 5

poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --retrieval-enabled \
  --knowledge-source-paths data/knowledge/runbooks \
  --knowledge-source-paths data/knowledge/incidents
```

## API usage

Endpoint:
- `POST /analyze-pipeline`

Request fields:
- `logs_path`
- `metrics_path`
- `config_path` (optional)
- `artifact_root` (optional)
- `bucket_size_minutes` (optional)
- `retrieval_enabled` (optional)
- `knowledge_source_paths` (optional)

## Artifact structure

For each run (`<artifact_root>/<run_id>/`):
- `normalized/timeline.json`
- `anomalies/anomalies.json`
- `incidents/incidents.json`
- `rca/rca_hypotheses.json`
- `reports/final_reports.json`
- `run_summary.json`

## Report export formats

One persisted report can be exported via CLI as:
- JSON
- Markdown
- HTML

Example:

```bash
poetry run incident-agent export-report \
  --artifact-dir artifacts/pipeline/<run_id> \
  --output-path report.html
```

A polished sample HTML export is included at `docs/sample_incident_report.html`.

## Sample scenario

Use the bundled scenario:
- logs: `data/sample/incident/anomaly_logs.csv`
- metrics: `data/sample/incident/anomaly_metrics.csv`

This scenario should produce at least one final report in the artifacts directory.

## Runtime observability

Pipeline execution logs machine-readable JSON events for:
- stage start/end/failure
- stage counts
- stage timing (`duration_ms`)
- run-level lifecycle (`pipeline.run.*`)

Provider retries and failures are also logged by the OpenAI adapter.

See `docs/observability.md` for event names and correlation fields.

## Resilience behavior

The pipeline now supports:
- bounded provider retries via `llm.max_retries` and `llm.retry_backoff_seconds`
- deterministic LLM response caching via `resilience.enable_llm_cache`
- intermediate stage caching via `resilience.enable_intermediate_cache`
- degraded execution when only one dataset is available
- failure summaries in `run_summary.json` for incomplete runs

Relevant config keys in `configs/default.yaml`:
- `resilience.enable_llm_cache`
- `resilience.llm_cache_dir`
- `resilience.enable_intermediate_cache`
- `resilience.intermediate_cache_dir`
- `resilience.allow_missing_logs`
- `resilience.allow_missing_metrics`
- `knowledge.enabled`
- `knowledge.source_paths`
- `knowledge.top_k`
- `knowledge.max_snippet_chars`
