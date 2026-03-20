install:
	poetry install

lint:
	poetry run ruff check .
	poetry run mypy src tests

test:
	poetry run pytest

run-api:
	poetry run uvicorn incident_agent.api.main:app --reload

run-demo:
	poetry run incident-agent --logs data/sample/logs.jsonl --metrics data/sample/metrics.jsonl
