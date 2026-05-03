"""External data connectors."""

from incident_agent.connectors.prometheus import fetch_prometheus_metrics
from incident_agent.core.settings import PrometheusConfig

__all__ = ["PrometheusConfig", "fetch_prometheus_metrics"]
