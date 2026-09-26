"""Failure contracts for file-backed incident input and output."""

from __future__ import annotations

from pathlib import Path

import pytest
from dataexcept import DataLoadingError, FileWriteError

from incident_agent.core.settings import load_settings_from_yaml
from incident_agent.ingestion.logs import ingest_logs
from incident_agent.ingestion.metrics import ingest_metrics
from incident_agent.utils.file_io import read_json, write_text


@pytest.mark.parametrize("filename", ["missing.csv", "missing.jsonl"])
def test_missing_input_retains_source_and_original_error(tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    with pytest.raises(DataLoadingError) as raised:
        if path.suffix == ".csv":
            ingest_logs(path)
        else:
            ingest_metrics(path)

    assert raised.value.source == str(path)
    assert isinstance(raised.value.original, FileNotFoundError)


def test_malformed_config_retains_yaml_parser_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("settings: [unclosed", encoding="utf-8")

    with pytest.raises(DataLoadingError) as raised:
        load_settings_from_yaml(path)

    assert raised.value.source == str(path)
    assert raised.value.original is not None


def test_malformed_artifact_retains_json_parser_error(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(DataLoadingError) as raised:
        read_json(path)

    assert raised.value.source == str(path)
    assert isinstance(raised.value.original, ValueError)


def test_unwritable_artifact_retains_destination_and_original_error(tmp_path: Path) -> None:
    blocker = tmp_path / "existing-file"
    blocker.write_text("content", encoding="utf-8")
    path = blocker / "report.json"

    with pytest.raises(FileWriteError) as raised:
        write_text(path, "{}")

    assert raised.value.path == str(blocker)
    assert isinstance(raised.value.original, OSError)
