# Runbook Ingestion and Chunking

## Purpose

Load operational runbooks as retrieval context so reports can include procedure-oriented guidance.

## Supported Inputs

- Markdown: `.md`
- Plain text: `.txt`, `.log`

## Chunking Strategy

- Markdown is chunked by section heading and paragraph boundaries.
- Each chunk preserves section metadata in the normalized text:
  - `section=<heading> | content=<paragraph>`
- Plain text is chunked by blank-line paragraph boundaries.

## Malformed Input Behavior

- Oversized files (over internal size cap) are skipped.
- Malformed JSON files in configured knowledge paths are skipped without failing the run.
- Unreadable files are ignored to keep retrieval best-effort.

## Usage

```bash
poetry run incident-agent run-pipeline \
  --logs data/sample/incident/anomaly_logs.csv \
  --metrics data/sample/incident/anomaly_metrics.csv \
  --retrieval-enabled \
  --knowledge-source-paths data/knowledge/runbooks
```
