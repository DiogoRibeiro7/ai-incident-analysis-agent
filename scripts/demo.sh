#!/usr/bin/env bash
set -euo pipefail

poetry run incident-agent \
  --logs data/sample/logs.jsonl \
  --metrics data/sample/metrics.jsonl
