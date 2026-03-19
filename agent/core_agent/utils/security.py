import logging
import os
from typing import Any
from urllib.parse import urlparse

import google.auth
import google.oauth2.id_token
from google.auth.transport.requests import Request


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def get_id_token(audience: str) -> str | None:
    """
    Generate a valid ID token to call a GCP service such as Cloud Run.

    It first tries the metadata server (when running on GCP) and then falls back to
    local ADC credentials for development.
    """
    request = Request()
    try:
        logging.debug("Retrieving ID token from metadata server for audience %s", audience)
        id_token = google.oauth2.id_token.fetch_id_token(request, audience)
        logging.debug("ID token successfully retrieved from metadata server")
        return id_token
    except Exception as exc:
        logging.debug("Metadata-server ID token retrieval failed: %s", exc)

    try:
        logging.debug("Retrieving ID token from local ADC credentials")
        credentials, _ = google.auth.default()
        credentials.refresh(request)
        id_token = getattr(credentials, "id_token", None)
        if id_token:
            logging.debug("ID token retrieved from local ADC credentials")
            return id_token
        logging.warning("ADC credentials did not yield an ID token")
    except Exception as exc:
        logging.warning("Unable to obtain ID token from local ADC credentials: %s", exc)

    return None