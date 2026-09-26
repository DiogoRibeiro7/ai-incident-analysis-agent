"""Resilience helpers for caching and degraded execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from dataexcept import DataLoadingError, FileWriteError

from incident_agent.utils.file_io import ensure_directory, read_json, write_text


def stable_cache_key(*parts: object) -> str:
    """Return a stable hash for cacheable inputs."""

    payload = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class JsonFileCache:
    """Simple JSON file cache for deterministic artifacts."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def read(self, key: str) -> dict[str, Any] | None:
        path = self._root / f"{key}.json"
        if not path.exists():
            return None
        loaded = read_json(path)
        if not isinstance(loaded, dict):
            return None
        return loaded

    def write(self, key: str, payload: dict[str, Any]) -> None:
        ensure_directory(self._root)
        path = self._root / f"{key}.json"
        temp_path = path.with_suffix(".json.tmp")
        write_text(temp_path, json.dumps(payload, indent=2))
        try:
            temp_path.replace(path)
        except OSError as exc:
            raise FileWriteError(str(path), exc) from exc


def file_fingerprint(path: str | Path) -> dict[str, object]:
    """Capture path metadata used to invalidate caches across input changes."""

    candidate = Path(path)
    if not candidate.exists():
        return {"path": str(candidate), "exists": False}
    try:
        stat = candidate.stat()
    except OSError as exc:
        raise DataLoadingError(str(candidate), exc) from exc
    return {
        "path": str(candidate),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
