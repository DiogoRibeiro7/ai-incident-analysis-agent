"""Security helpers for path safety and configuration hardening warnings."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from incident_agent.core.settings import (
    SecurityConfig,
    load_security_config,
    load_settings_from_yaml,
)

_SECRET_KEYWORDS = ("token", "secret", "password", "api_key", "apikey", "webhook_url")


def validate_read_path(path: str | Path, *, config: SecurityConfig, workspace_root: Path) -> None:
    """Ensure read path is constrained to approved roots."""

    if not config.enabled:
        return
    resolved = _resolve_under_workspace(path, workspace_root=workspace_root)
    allowed_roots = _resolve_allowed_roots(config.allowed_read_paths, workspace_root=workspace_root)
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise ValueError(f"Read path not allowed by security policy: {path}")


def validate_write_path(path: str | Path, *, config: SecurityConfig, workspace_root: Path) -> None:
    """Ensure write path is constrained to approved roots."""

    if not config.enabled:
        return
    resolved = _resolve_under_workspace(path, workspace_root=workspace_root)
    allowed_roots = _resolve_allowed_roots(
        config.allowed_write_paths,
        workspace_root=workspace_root,
    )
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise ValueError(f"Write path not allowed by security policy: {path}")


def load_security_config_safe(config_path: str | Path) -> SecurityConfig:
    """Load security config and fallback to defaults on invalid files."""

    try:
        return load_security_config(config_path)
    except Exception:
        return SecurityConfig()


def config_security_warnings(config_path: str | Path) -> list[str]:
    """Return non-fatal config warnings for potential security issues."""

    warnings: list[str] = []
    loaded = load_settings_from_yaml(Path(config_path))
    _walk_for_plaintext_secrets(loaded, prefix="", warnings=warnings)

    llm_section = loaded.get("llm")
    if isinstance(llm_section, dict) and llm_section.get("provider") == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            warnings.append("OPENAI_API_KEY is not set while llm.provider=openai.")
    return warnings


def _walk_for_plaintext_secrets(
    node: object, *, prefix: str, warnings: list[str]
) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            lowered = str(key).lower()
            if any(token in lowered for token in _SECRET_KEYWORDS) and isinstance(value, str):
                stripped = value.strip()
                if stripped and not stripped.startswith("${") and "example" not in stripped.lower():
                    warnings.append(
                        f"Potential plaintext secret in config key '{next_prefix}'."
                    )
            _walk_for_plaintext_secrets(value, prefix=next_prefix, warnings=warnings)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_for_plaintext_secrets(value, prefix=f"{prefix}[{index}]", warnings=warnings)


def _resolve_under_workspace(path: str | Path, *, workspace_root: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    return candidate.resolve(strict=False)


def _resolve_allowed_roots(values: list[str], *, workspace_root: Path) -> list[Path]:
    roots: list[Path] = []
    for value in values:
        root = Path(value)
        if not root.is_absolute():
            root = workspace_root / root
        roots.append(root.resolve(strict=False))
    roots.append(Path(tempfile.gettempdir()).resolve(strict=False))
    return roots


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
