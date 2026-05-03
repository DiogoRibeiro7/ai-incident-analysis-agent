from __future__ import annotations

from pathlib import Path

import pytest

from incident_agent.core.settings import SecurityConfig
from incident_agent.utils.security import (
    config_security_warnings,
    validate_read_path,
    validate_write_path,
)


def test_validate_read_path_blocks_outside_allowlist() -> None:
    config = SecurityConfig(allowed_read_paths=["data"], allowed_write_paths=["artifacts"])
    with pytest.raises(ValueError):
        validate_read_path(
            "C:/windows/system32/drivers/etc/hosts",
            config=config,
            workspace_root=Path.cwd(),
        )


def test_validate_write_path_allows_artifacts_subdir() -> None:
    config = SecurityConfig(allowed_read_paths=["data"], allowed_write_paths=["artifacts"])
    validate_write_path(
        "artifacts/pipeline",
        config=config,
        workspace_root=Path.cwd(),
    )


def test_config_security_warnings_detect_plaintext_secret(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  provider: openai",
                "webhook_export:",
                "  secret_token: abc123",
            ]
        ),
        encoding="utf-8",
    )
    warnings = config_security_warnings(config_path)
    assert any("plaintext secret" in item.lower() for item in warnings)
