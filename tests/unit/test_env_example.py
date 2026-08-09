from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = REPO_ROOT / ".env.example"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
SECRET_NAME_PARTS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def parse_env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        assert separator == "=", f"invalid .env.example line: {line!r}"
        values[key] = value
    return values


def git_returns_success(*args: str) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def test_env_example_is_committed_and_not_ignored() -> None:
    assert ENV_EXAMPLE.exists()
    assert git_returns_success("ls-files", "--error-unmatch", ".env.example")
    assert not git_returns_success("check-ignore", "--no-index", ".env.example")
    assert git_returns_success("check-ignore", "--no-index", ".env")
    assert git_returns_success("check-ignore", "--no-index", ".env.local")


def test_env_example_contains_docker_runtime_variables() -> None:
    values = parse_env_example()
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    compose_variables = set(re.findall(r"\$\{([A-Z0-9_]+)(?::-[^}]*)?}", compose_text))

    assert compose_variables <= values.keys()


def test_env_example_does_not_contain_secret_values() -> None:
    failures = [
        key
        for key, value in parse_env_example().items()
        if any(part in key for part in SECRET_NAME_PARTS) and value.strip()
    ]

    assert failures == []
