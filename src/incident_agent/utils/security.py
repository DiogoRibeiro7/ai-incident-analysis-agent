"""Security helpers for path safety and configuration hardening warnings."""

from __future__ import annotations

import os
import socket
import tempfile
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse

from incident_agent.core.settings import (
    SecurityConfig,
    load_security_config,
    load_settings_from_yaml,
)

_SECRET_KEYWORDS = ("token", "secret", "password", "api_key", "apikey", "webhook_url")


class PathPolicyError(ValueError):
    """Raised when a filesystem path violates the configured security policy."""


class OutboundUrlPolicyError(ValueError):
    """Raised when an outbound URL violates the configured security policy."""


def validate_outbound_url(
    url: str,
    *,
    allowed_hosts: list[str],
    allowed_schemes: set[str],
    allow_private_networks: bool,
) -> str:
    """Validate an outbound HTTP URL before network access."""

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes:
        raise OutboundUrlPolicyError(f"Outbound URL scheme is not allowed: {scheme or '<empty>'}")
    if parsed.username or parsed.password:
        raise OutboundUrlPolicyError("Outbound URL credentials are not allowed.")
    host = parsed.hostname
    if host is None or not host.strip():
        raise OutboundUrlPolicyError("Outbound URL must include a hostname.")
    normalized_host = host.strip().lower().rstrip(".")
    if not _host_allowed(normalized_host, allowed_hosts):
        raise OutboundUrlPolicyError(f"Outbound URL host is not in the allowlist: {host}")

    _validate_resolved_host(
        normalized_host,
        allow_private_networks=allow_private_networks,
    )
    return url


def validate_read_path(path: str | Path, *, config: SecurityConfig, workspace_root: Path) -> None:
    """Ensure read path is constrained to approved roots."""

    _validate_read_path(
        path,
        config=config,
        workspace_root=workspace_root,
        include_system_temp=True,
    )


def validate_retrieval_path(
    path: str | Path,
    *,
    config: SecurityConfig,
    workspace_root: Path,
) -> None:
    """Ensure retrieval source paths are constrained to configured read roots."""

    _validate_read_path(
        path,
        config=config,
        workspace_root=workspace_root,
        include_system_temp=False,
    )


def validate_write_path(path: str | Path, *, config: SecurityConfig, workspace_root: Path) -> None:
    """Ensure write path is constrained to approved roots."""

    if not config.enabled:
        return
    resolved = _resolve_under_workspace(path, workspace_root=workspace_root)
    allowed_roots = _resolve_allowed_roots(
        config.allowed_write_paths,
        workspace_root=workspace_root,
        include_system_temp=True,
    )
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise PathPolicyError(f"Write path not allowed by security policy: {path}")


def _validate_read_path(
    path: str | Path,
    *,
    config: SecurityConfig,
    workspace_root: Path,
    include_system_temp: bool,
) -> None:
    if not config.enabled:
        return
    resolved = _resolve_under_workspace(path, workspace_root=workspace_root)
    allowed_roots = _resolve_allowed_roots(
        config.allowed_read_paths,
        workspace_root=workspace_root,
        include_system_temp=include_system_temp,
    )
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise PathPolicyError(f"Read path not allowed by security policy: {path}")


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


def _walk_for_plaintext_secrets(node: object, *, prefix: str, warnings: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            lowered = str(key).lower()
            if any(token in lowered for token in _SECRET_KEYWORDS) and isinstance(value, str):
                stripped = value.strip()
                if stripped and not stripped.startswith("${") and "example" not in stripped.lower():
                    warnings.append(f"Potential plaintext secret in config key '{next_prefix}'.")
            _walk_for_plaintext_secrets(value, prefix=next_prefix, warnings=warnings)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_for_plaintext_secrets(value, prefix=f"{prefix}[{index}]", warnings=warnings)


def _resolve_under_workspace(path: str | Path, *, workspace_root: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    return candidate.resolve(strict=False)


def _host_allowed(host: str, allowed_hosts: list[str]) -> bool:
    for value in allowed_hosts:
        allowed = value.strip().lower().rstrip(".")
        if not allowed:
            continue
        if allowed.startswith("*.") and host.endswith(allowed[1:]):
            return True
        if host == allowed:
            return True
    return False


def _validate_resolved_host(host: str, *, allow_private_networks: bool) -> None:
    try:
        addresses = [ip_address(host)]
    except ValueError:
        try:
            resolved = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as error:
            raise OutboundUrlPolicyError(
                f"Outbound URL host could not be resolved: {host}"
            ) from error
        addresses = sorted({ip_address(item[4][0]) for item in resolved}, key=str)

    for address in addresses:
        if _blocked_outbound_address(address) and not allow_private_networks:
            raise OutboundUrlPolicyError(
                f"Outbound URL resolves to a disallowed address: {address}"
            )


def _blocked_outbound_address(address: object) -> bool:
    return bool(
        getattr(address, "is_loopback", False)
        or getattr(address, "is_private", False)
        or getattr(address, "is_link_local", False)
        or getattr(address, "is_multicast", False)
        or getattr(address, "is_reserved", False)
        or getattr(address, "is_unspecified", False)
    )


def _resolve_allowed_roots(
    values: list[str],
    *,
    workspace_root: Path,
    include_system_temp: bool,
) -> list[Path]:
    roots: list[Path] = []
    for value in values:
        root = Path(value)
        if not root.is_absolute():
            root = workspace_root / root
        roots.append(root.resolve(strict=False))
    if include_system_temp:
        roots.append(Path(tempfile.gettempdir()).resolve(strict=False))
    return roots


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
