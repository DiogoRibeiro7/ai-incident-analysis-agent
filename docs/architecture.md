# Architecture

## High-level flow

1. Ingestion layer loads logs and metrics.
2. Normalization layer converts timestamps to UTC and aligns events into time buckets.
3. Correlation layer groups suspicious signals into incident candidates.
4. Prompt layer prepares grounded context.
5. LLM layer produces a structured report.
6. Validation layer ensures a predictable response schema.
7. Delivery layer exposes results through CLI and API.

## Extension points

- Real observability connectors under `clients/`
- Retrieval over runbooks and previous incidents
- Multi-stage agent workflows
- Evaluation and observability for prompt and model quality
