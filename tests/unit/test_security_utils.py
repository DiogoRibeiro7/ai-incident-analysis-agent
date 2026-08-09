from __future__ import annotations

from pathlib import Path

import pytest

from incident_agent.core.settings import SecurityConfig
from incident_agent.utils.security import (
    config_security_warnings,
    validate_outbound_url,
    validate_read_path,
    validate_retrieval_path,
    validate_write_path,
)

_PUBLIC_TEST_HOST = "93.184.216.34"


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


def test_validate_retrieval_path_blocks_temp_path_outside_allowlist(tmp_path: Path) -> None:
    config = SecurityConfig(allowed_read_paths=["data"], allowed_write_paths=["artifacts"])
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="Read path not allowed"):
        validate_retrieval_path(secret, config=config, workspace_root=Path.cwd())


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:9090",
        "http://127.0.0.1:9090",
        "http://[::1]:9090",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.2/hook",
        "not-a-url",
    ],
)
def test_validate_outbound_url_rejects_blocked_destinations(url: str) -> None:
    with pytest.raises(ValueError):
        validate_outbound_url(
            url,
            allowed_hosts=["localhost", "127.0.0.1", "::1", "169.254.169.254", "10.0.0.2"],
            allowed_schemes={"http", "https"},
            allow_private_networks=False,
        )


def test_validate_outbound_url_allows_explicit_public_https_host() -> None:
    validate_outbound_url(
        f"https://{_PUBLIC_TEST_HOST}/webhook",
        allowed_hosts=[_PUBLIC_TEST_HOST],
        allowed_schemes={"https"},
        allow_private_networks=False,
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
