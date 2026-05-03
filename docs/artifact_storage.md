# External Artifact Storage

## Goal

Persist pipeline artifacts locally by default and optionally mirror them to external storage.

## Backends

- `local` (default): writes only to local filesystem under `artifact_root/<run_id>/`
- `s3`: writes locally and mirrors all artifact files to an S3-compatible bucket

## Configuration

Set in `configs/default.yaml`:

```yaml
artifact_storage:
  backend: local
  s3_bucket: null
  s3_prefix: incident-agent-artifacts
  s3_region: null
  s3_endpoint_url: null
```

For S3-compatible storage:

- set `backend: s3`
- set `s3_bucket`
- optionally set `s3_region` and `s3_endpoint_url` (for MinIO or other S3-compatible APIs)

## Behavior

- Local artifacts are always written first.
- When `backend: s3`, every generated artifact file is uploaded with key:
  - `<s3_prefix>/<run_id>/<relative_path>`
- If S3 backend is selected without `boto3`, pipeline fails with a clear configuration error.
