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

## Error handling behavior

OpenAI provider includes:
- request timeout handling
- bounded retries for rate limits (`429`) and transient failures (`5xx`/network)
- malformed JSON response handling

If provider calls fail during incident analysis, the agent degrades gracefully by returning a structured fallback `IncidentReport` with `provider_error` evidence instead of crashing the workflow.

## Configuration and credentials

Config section in `configs/default.yaml`:
- `llm.provider`
- `llm.report_model`
- `llm.completion_model`
- `llm.timeout_seconds`
- `llm.max_retries`
- `llm.retry_backoff_seconds`

Environment variable for OpenAI:
- `INCIDENT_AGENT_OPENAI_API_KEY`
