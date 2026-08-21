import logging
from loguru import logger
import google.cloud.logging


class PropagateHandler(logging.Handler):
    """
    A custom logging handler that routes loguru logs to the standard python
    logging module. This allows google-cloud-logging setup to intercept
    these logs properly and retain the correct severity levels.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Retrieve the logger corresponding to the original loguru context
        logging.getLogger(record.name).handle(record)


def setup_observability() -> None:
    """
    Initializes OpenTelemetry exporters and hooks Loguru into standard Python
    logging, which is intercepted by google.cloud.logging.

    This ensures that logs correctly define their real level in Cloud Logging
    instead of just outputting everything as INFO to stderr.
    """
    # 1. Initialize Google Cloud Logging standard handler
    client = google.cloud.logging.Client()
    client.setup_logging()

    # 2. Redirect Loguru to standard Python logging
    # Remove the default loguru stderr handler if it exists
    logger.remove()

    # Add our PropagateHandler to loguru
    logger.add(PropagateHandler(), format="{message}")

    # Note: OpenTelemetry auto-instrumentation is driven by environment variables
    # injected via `.env` (or CI/CD runtime variables), such as `OTEL_TRACES_EXPORTER=gcp_trace`
    # The ADK runtime automatically instruments underlying models and traces.
