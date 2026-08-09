FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock* ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

COPY README.md ./
COPY src ./src
RUN poetry install --only-root --no-interaction --no-ansi

COPY configs ./configs
COPY data ./data
COPY eval ./eval

EXPOSE 8000

CMD ["uvicorn", "incident_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
