"""Structured logging and lightweight tracing utilities."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from time import perf_counter

_RUN_ID: ContextVar[str | None] = ContextVar("run_id", default=None)
_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
_LOGGING_CONFIGURED = False

_RESERVED_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
}


class JsonLogFormatter(logging.Formatter):
    """Render log records as a single JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        if isinstance(event, str):
            payload["event"] = event

        run_id = getattr(record, "run_id", None) or _RUN_ID.get()
        if isinstance(run_id, str):
            payload["run_id"] = run_id
        request_id = getattr(record, "request_id", None) or _REQUEST_ID.get()
        if isinstance(request_id, str):
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key in payload:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return logger instance used by project modules."""

    return logging.getLogger(name)


def configure_logging(*, level: str = "INFO", json_logs: bool = True) -> None:
    """Configure root logging in an idempotent way."""

    global _LOGGING_CONFIGURED
    root = logging.getLogger()
    root.setLevel(level.upper())

    if _LOGGING_CONFIGURED:
        return

    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root.handlers.clear()
    root.addHandler(handler)
    _LOGGING_CONFIGURED = True


@contextmanager
def bind_context(*, run_id: str | None = None, request_id: str | None = None) -> Iterator[None]:
    """Bind run/request identifiers to logging context."""

    run_token: Token[str | None] | None = None
    request_token: Token[str | None] | None = None
    if run_id is not None:
        run_token = _RUN_ID.set(run_id)
    if request_id is not None:
        request_token = _REQUEST_ID.set(request_id)
    try:
        yield
    finally:
        if run_token is not None:
            _RUN_ID.reset(run_token)
        if request_token is not None:
            _REQUEST_ID.reset(request_token)


def log_event(
    logger: logging.Logger,
    *,
    level: int,
    event: str,
    message: str,
    **fields: object,
) -> None:
    """Emit a structured logging event."""

    logger.log(level, message, extra={"event": event, **fields})


@contextmanager
def execution_span(
    logger: logging.Logger,
    *,
    event_prefix: str,
    stage: str,
    **fields: object,
) -> Iterator[None]:
    """Log stage start/end/failure with timing."""

    start = perf_counter()
    log_event(
        logger,
        level=logging.INFO,
        event=f"{event_prefix}.start",
        message=f"{stage} started",
        stage=stage,
        **fields,
    )
    try:
        yield
    except Exception as error:
        duration_ms = round((perf_counter() - start) * 1000, 2)
        log_event(
            logger,
            level=logging.ERROR,
            event=f"{event_prefix}.failed",
            message=f"{stage} failed",
            stage=stage,
            duration_ms=duration_ms,
            error_type=type(error).__name__,
            error=str(error),
            **fields,
        )
        raise
    duration_ms = round((perf_counter() - start) * 1000, 2)
    log_event(
        logger,
        level=logging.INFO,
        event=f"{event_prefix}.completed",
        message=f"{stage} completed",
        stage=stage,
        duration_ms=duration_ms,
        **fields,
    )
