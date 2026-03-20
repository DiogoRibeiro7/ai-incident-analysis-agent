"""Ingestion utilities for logs and metrics."""

from incident_agent.ingestion.common import DataQualityReport, IngestionResult
from incident_agent.ingestion.logs import ingest_logs
from incident_agent.ingestion.metrics import ingest_metrics

__all__ = [
    "DataQualityReport",
    "IngestionResult",
    "ingest_logs",
    "ingest_metrics",
]
