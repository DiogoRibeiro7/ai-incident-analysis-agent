"""Path-aware file operations used by ingestion and artifact workflows."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

import yaml
from dataexcept import DataLoadingError, FileWriteError


@contextmanager
def open_input(path: str | Path, *, newline: str | None = None) -> Iterator[TextIO]:
    """Open UTF-8 input while preserving the path and original I/O error."""

    source = Path(path)
    try:
        with source.open("r", encoding="utf-8", newline=newline) as handle:
            yield handle
    except (OSError, UnicodeError) as exc:
        raise DataLoadingError(str(source), exc) from exc


def read_text(path: str | Path) -> str:
    """Read UTF-8 text with a source-aware error."""

    with open_input(path) as handle:
        return handle.read()


def read_json(path: str | Path) -> Any:  # noqa: ANN401
    """Read a JSON document with a source-aware read or decode error."""

    source = Path(path)
    try:
        return json.loads(read_text(source))
    except json.JSONDecodeError as exc:
        raise DataLoadingError(str(source), exc) from exc


def read_yaml(path: str | Path) -> Any:  # noqa: ANN401
    """Read YAML, leaving domain schema checks to the caller."""

    source = Path(path)
    try:
        return yaml.safe_load(read_text(source))
    except yaml.YAMLError as exc:
        raise DataLoadingError(str(source), exc) from exc


def ensure_directory(path: str | Path) -> Path:
    """Create an output directory with a path-aware failure."""

    destination = Path(path)
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FileWriteError(str(destination), exc) from exc
    return destination


@contextmanager
def open_output(path: str | Path, *, append: bool = False) -> Iterator[TextIO]:
    """Write UTF-8 text to a file, creating its parent directory."""

    destination = Path(path)
    ensure_directory(destination.parent)
    try:
        with destination.open("a" if append else "w", encoding="utf-8") as handle:
            yield handle
    except (OSError, UnicodeError) as exc:
        raise FileWriteError(str(destination), exc) from exc


def write_text(path: str | Path, content: str) -> None:
    """Persist UTF-8 text with a destination-aware error."""

    with open_output(path) as handle:
        handle.write(content)
