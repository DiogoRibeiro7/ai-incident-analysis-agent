# LLM Provider Abstraction

## Goal

Decouple report generation from a single mock implementation and support interchangeable providers with robust failure handling.

## Interfaces and implementations

- `src/incident_agent/llm/base.py`
  - `BaseLLMProvider`
  - provider error types (`LLMProviderError`, `LLMTimeoutError`, `LLMRateLimitError`, `LLMResponseFormatError`)
- `src/incident_agent/llm/mock.py`
  - `MockLLMProvider`
- `src/incident_agent/llm/openai_provider.py`
  - `OpenAIProvider`
- `src/incident_agent/llm/factory.py`
  - `LLMConfig`
  - `load_llm_config(...)`
  - `create_provider(...)`

## Request/response models

Defined in `src/incident_agent/schemas/llm.py`:
- `LLMCompletionRequest` / `LLMCompletionResponse`
- `LLMStructuredReportRequest` / `LLMStructuredReportResponse`
- `LLMUsage` (prompt tokens, completion tokens, total tokens, latency, estimated cost)

## Error handling behavior

OpenAI provider includes:
- request timeout handling
- bounded retries for rate limits (`429`) and transient failures (`5xx`/network)
- malformed JSON response handling

In the end-to-end pipeline, provider failures degrade report generation rather than discarding upstream artifacts. The run summary records warnings and failure summaries for incomplete runs.

## Configuration and credentials

Config section in `configs/default.yaml`:
- `llm.provider`
- `llm.report_model`
- `llm.completion_model`
- `llm.timeout_seconds`
- `llm.max_retries`
- `llm.retry_backoff_seconds`
- `llm.model_pricing_usd_per_1k_tokens`

Environment variable for OpenAI:
- `INCIDENT_AGENT_OPENAI_API_KEY`

`INCIDENT_AGENT_OPENAI_API_KEY` is the canonical key name used by both runtime
provider initialization and configuration security warnings. The generic
`OPENAI_API_KEY` variable is not read by this project; set the repository
specific variable instead.
