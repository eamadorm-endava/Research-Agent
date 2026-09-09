import logging
from typing import Optional
from loguru import logger
import google.cloud.logging
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from google.adk.telemetry.google_cloud import get_gcp_exporters, get_gcp_resource
from google.adk.telemetry.setup import maybe_set_otel_providers
from .config.agent_settings import GCP_CONFIG


class PropagateHandler(logging.Handler):
    """
    A custom logging handler that routes loguru logs to the standard python
    logging module. This allows google-cloud-logging setup to intercept
    these logs properly and retain the correct severity levels.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Retrieve the logger corresponding to the original loguru context
        logging.getLogger(record.name).handle(record)


def _setup_cloud_logging() -> None:
    """
    Configures Google Cloud Logging and bridges Loguru output.

    Args:
        None

    Returns:
        None
    """
    try:
        client = google.cloud.logging.Client()
        client.setup_logging()
    except Exception as err:
        logger.debug(f"Cloud Logging skipped (running locally or without ADC): {err}")

    logger.remove()
    logger.add(PropagateHandler(), format="{message}")


def _setup_cloud_metrics(project_id: Optional[str] = None) -> None:
    """
    Initializes OpenTelemetry MeterProvider with Cloud Monitoring exporter.

    Args:
        project_id: Optional[str] -> Target GCP project ID for metrics

    Returns:
        None
    """
    if isinstance(metrics.get_meter_provider(), MeterProvider):
        return

    resolved_project_id = project_id or GCP_CONFIG.PROJECT_ID
    try:
        hooks = get_gcp_exporters(
            enable_cloud_tracing=True,
            enable_cloud_metrics=True,
            enable_cloud_logging=False,
        )
        resource = get_gcp_resource(project_id=resolved_project_id)
        maybe_set_otel_providers(
            otel_hooks_to_setup=[hooks],
            otel_resource=resource,
        )
        logger.info("OpenTelemetry Cloud Monitoring metrics provider initialized.")
    except Exception as err:
        logger.warning(f"Could not initialize Cloud Monitoring metrics provider: {err}")


def setup_observability(project_id: Optional[str] = None) -> None:
    """
    Initializes both Cloud Logging and OpenTelemetry Cloud Monitoring metrics.

    Args:
        project_id: Optional[str] -> Target GCP project ID for metrics

    Returns:
        None
    """
    _setup_cloud_logging()
    _setup_cloud_metrics(project_id=project_id)
