# Architecture

## High-level flow

1. Ingestion layer loads logs and metrics.
2. Normalization layer converts timestamps to UTC and aligns events into time buckets.
3. Anomaly detection layer applies robust statistical rules per service and globally.
4. Correlation layer groups nearby anomalies into incident candidates and ranks likely root service with dependency hints.
5. RCA layer ranks evidence, summarizes incident features, and produces root-cause hypotheses.
6. Prompt layer prepares grounded context.
7. Prompt template renderer builds modular report prompts from RCA artifacts.
8. Optional retrieval adds cited runbook, historical incident, or Grafana annotation context.
9. LLM provider abstraction selects mock or OpenAI backends for structured report generation.
10. Validation layer checks response schema and generated claim grounding.
11. Pipeline orchestrator persists normalized data, anomalies, incidents, RCA artifacts, grounding summaries, and final reports.
12. Delivery layer exposes results through CLI, API, file exports, review transitions, and approved-report webhooks.

## Potential extension points

- Additional observability connectors for CloudWatch, Datadog, and Grafana metrics APIs
- Richer retrieval ranking and metadata filters
- Multi-stage review and remediation workflows
- Production deployment manifests and authentication layers
