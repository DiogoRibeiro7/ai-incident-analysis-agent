"""Resilience helpers for caching and degraded execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


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
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return None
        return loaded

    def write(self, key: str, payload: dict[str, Any]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{key}.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)


def file_fingerprint(path: str | Path) -> dict[str, object]:
    """Capture path metadata used to invalidate caches across input changes."""

    candidate = Path(path)
    if not candidate.exists():
        return {"path": str(candidate), "exists": False}
    stat = candidate.stat()
    return {
        "path": str(candidate),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
