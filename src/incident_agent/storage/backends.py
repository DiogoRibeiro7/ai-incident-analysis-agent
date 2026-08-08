"""Artifact storage backends for pipeline outputs."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

from incident_agent.core.settings import ArtifactStorageConfig


class _S3ClientFactory(Protocol):
    def client(self, service_name: str, **kwargs: object) -> object: ...


@runtime_checkable
class _UploadClient(Protocol):
    def upload_file(self, filename: str, bucket: str, key: str) -> None: ...


def mirror_artifacts_to_backend(*, run_dir: Path, config: ArtifactStorageConfig) -> None:
    """Mirror locally persisted artifacts to configured external backend."""

    if config.backend == "local":
        return
    if config.backend == "s3":
        _mirror_to_s3(run_dir=run_dir, config=config)
        return
    raise ValueError(f"Unsupported artifact storage backend: {config.backend}")


def _mirror_to_s3(*, run_dir: Path, config: ArtifactStorageConfig) -> None:
    if not config.s3_bucket:
        raise ValueError("artifact_storage.s3_bucket is required when backend=s3")

    boto3 = _load_boto3()

    client = boto3.client(
        "s3",
        region_name=config.s3_region,
        endpoint_url=config.s3_endpoint_url,
    )
    if not isinstance(client, _UploadClient):
        raise ValueError("Configured S3 client does not implement upload_file().")
    prefix = config.s3_prefix.strip("/")
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(run_dir).as_posix()
        key = "/".join(part for part in [prefix, run_dir.name, relative] if part)
        client.upload_file(str(path), config.s3_bucket, key)


def _load_boto3() -> _S3ClientFactory:
    try:
        boto3 = import_module("boto3")
    except Exception as error:  # pragma: no cover
        raise ValueError(
            "backend=s3 requires boto3. "
            "Install dependency or switch artifact_storage.backend=local."
        ) from error
    return cast(_S3ClientFactory, boto3)
