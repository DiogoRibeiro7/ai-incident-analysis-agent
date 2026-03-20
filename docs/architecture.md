# Architecture

## High-level flow

1. Ingestion layer loads logs and metrics.
2. Correlation layer groups suspicious signals into incident candidates.
3. Prompt layer prepares grounded context.
4. LLM layer produces a structured report.
5. Validation layer ensures a predictable response schema.
6. Delivery layer exposes results through CLI and API.

## Extension points

- Real observability connectors under `clients/`
- Retrieval over runbooks and previous incidents
- Multi-stage agent workflows
- Evaluation and observability for prompt and model quality
