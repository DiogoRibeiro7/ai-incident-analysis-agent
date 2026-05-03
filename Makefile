install:
	poetry install

format-check:
	poetry run ruff format --check .

lint:
	poetry run ruff check .

typecheck:
	poetry run mypy src tests

test:
	poetry run pytest

test-unit:
	poetry run pytest --no-cov tests/unit

test-integration:
	poetry run pytest --no-cov tests/integration

coverage:
	poetry run pytest

quality:
	poetry run ruff format --check .
	poetry run ruff check .
	poetry run mypy src tests
	poetry run pytest

run-api:
	poetry run uvicorn incident_agent.api.main:app --reload

run-demo:
	poetry run incident-agent run-demo

docker-up:
	docker compose up --build
