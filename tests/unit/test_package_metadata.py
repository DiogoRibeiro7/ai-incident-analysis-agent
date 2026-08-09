from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast

from incident_agent import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]


def project_metadata() -> dict[str, object]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return cast(dict[str, object], pyproject["project"])


def test_package_version_is_exposed() -> None:
    package_version = str(project_metadata()["version"])

    assert __version__ == package_version


def test_package_metadata_matches_project_configuration() -> None:
    metadata = project_metadata()

    assert metadata["name"] == "ai-incident-analysis-agent"
    assert metadata["version"] == __version__
    assert metadata["license"] == "MIT"
    assert "incident-response" in cast(list[str], metadata["keywords"])
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    urls = cast(dict[str, str], cast(dict[str, Any], pyproject["project"])["urls"])
    assert urls["Repository"] == "https://github.com/DiogoRibeiro7/ai-incident-analysis-agent"


def test_citation_metadata_tracks_release_version() -> None:
    zenodo = json.loads((REPO_ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    citation = (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    package_version = str(project_metadata()["version"])

    assert zenodo["version"] == package_version
    assert f'version: "{package_version}"' in citation
