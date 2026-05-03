from __future__ import annotations

from pathlib import Path

import pytest

from incident_agent.core.settings import ArtifactStorageConfig
from incident_agent.storage.backends import mirror_artifacts_to_backend


def test_mirror_artifacts_local_backend_noop(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports" / "final_reports.json").write_text("{}", encoding="utf-8")
    mirror_artifacts_to_backend(
        run_dir=run_dir,
        config=ArtifactStorageConfig(backend="local"),
    )


def test_mirror_artifacts_s3_backend_uploads_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run-2"
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports" / "final_reports.json").write_text("{}", encoding="utf-8")
    (run_dir / "run_summary.json").write_text("{}", encoding="utf-8")

    uploaded: list[tuple[str, str]] = []

    class _FakeS3Client:
        def upload_file(self, local_path: str, bucket: str, key: str) -> None:
            assert Path(local_path).exists()
            uploaded.append((bucket, key))

    class _FakeBoto3Module:
        @staticmethod
        def client(_service: str, **_kwargs: object) -> _FakeS3Client:
            return _FakeS3Client()

    import incident_agent.storage.backends as backends

    monkeypatch.setattr(backends, "_load_boto3", lambda: _FakeBoto3Module)
    mirror_artifacts_to_backend(
        run_dir=run_dir,
        config=ArtifactStorageConfig(
            backend="s3",
            s3_bucket="demo-bucket",
            s3_prefix="pipeline-artifacts",
        ),
    )
    assert uploaded
    assert all(bucket == "demo-bucket" for bucket, _ in uploaded)
    assert any("run-2/reports/final_reports.json" in key for _, key in uploaded)


def test_mirror_artifacts_s3_backend_requires_bucket(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-3"
    run_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="s3_bucket"):
        mirror_artifacts_to_backend(
            run_dir=run_dir,
            config=ArtifactStorageConfig(backend="s3", s3_bucket=None),
        )
