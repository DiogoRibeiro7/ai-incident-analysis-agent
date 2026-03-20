# Architecture

## High-level flow

1. Ingestion layer loads logs and metrics.
2. Normalization layer converts timestamps to UTC and aligns events into time buckets.
3. Anomaly detection layer applies robust statistical rules per service and globally.
4. Correlation layer groups nearby anomalies into incident candidates and ranks likely root service with dependency hints.
5. RCA layer ranks evidence, summarizes incident features, and produces root-cause hypotheses.
6. Prompt layer prepares grounded context.
7. Prompt template renderer builds modular report prompts from RCA artifacts.
8. LLM provider abstraction selects mock or OpenAI backends for structured report generation.
9. Validation layer ensures a predictable response schema.
10. Pipeline orchestrator persists normalized data, anomalies, incidents, RCA artifacts, and final reports.
11. Delivery layer exposes results through CLI and API.

## Extension points

- Real observability connectors under `clients/`
- Retrieval over runbooks and previous incidents
- Multi-stage agent workflows
- Evaluation and observability for prompt and model quality
