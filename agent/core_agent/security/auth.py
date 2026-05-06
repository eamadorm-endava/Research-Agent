import time
from typing import Optional

from loguru import logger

import google.auth
import google.oauth2.id_token
from google.auth.transport.requests import Request
from google.adk.agents.readonly_context import ReadonlyContext


# Global cache for ID tokens: {audience: (token, expiry_timestamp)}
_ID_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
TOKEN_TTL_SECONDS = (
    3000  # Reuse tokens for 50 minutes (standard GCP tokens last 1 hour)
)


def get_id_token(audience: str) -> Optional[str]:
    """Generates or retrieves a cached ID token for calling GCP-authenticated services.

    Checks the global cache first. If missing or expired, it tries the GCP metadata server,
    then falls back to local ADC credentials.

    Args:
        audience: str -> The target service URL used as the token audience.

    Returns:
        Optional[str] -> The ID token string, or None if retrieval fails.
    """
    now = time.time()

    # Check cache first
    if audience in _ID_TOKEN_CACHE:
        token, expiry = _ID_TOKEN_CACHE[audience]
        if expiry > now + 60:  # 1 minute buffer
            logger.debug(f"Using cached ID token for audience: {audience}")
            return token

    logger.info(f"Generating fresh ID token for audience: {audience}")
    request = Request()

    # Path 1: Metadata Server (Production/GCP)
    try:
        logger.debug(
            f"Retrieving ID token from metadata server for audience {audience}"
        )
        id_token = google.oauth2.id_token.fetch_id_token(request, audience)
        _ID_TOKEN_CACHE[audience] = (id_token, now + TOKEN_TTL_SECONDS)
        logger.debug("ID token successfully retrieved from metadata server and cached")
        return id_token
    except Exception as exc:
        logger.warning(f"Metadata-server ID token retrieval failed: {exc}")

    # Path 2: Local ADC (Development)
    try:
        logger.debug("Retrieving ID token from local ADC credentials")
        credentials, _ = google.auth.default()
        credentials.refresh(request)
        id_token = getattr(credentials, "id_token", None)
        if id_token:
            _ID_TOKEN_CACHE[audience] = (id_token, now + TOKEN_TTL_SECONDS)
            logger.debug("ID token retrieved from local ADC credentials and cached")
            return id_token
        logger.warning("ADC credentials did not yield an ID token")
    except Exception as exc:
        logger.warning(f"Unable to obtain ID token from local ADC credentials: {exc}")

    return None


def get_ge_oauth_token(
    readonly_context: ReadonlyContext, auth_id: str
) -> Optional[str]:
    """Retrieves the OAuth token injected by Gemini Enterprise for a given auth resource ID.

    Code adapted from: https://github.com/google/adk-docs/issues/1001#issuecomment-3894834825

    Args:
        readonly_context: ReadonlyContext -> The ADK readonly context holding session state.
        auth_id: str -> The Gemini Enterprise OAuth resource ID to look up.

    Returns:
        Optional[str] -> The OAuth token if present in session state, otherwise None.
    """
    logger.info(f"Getting OAuth token for {auth_id = }")
    oauth_token = readonly_context.state.get(auth_id)
    if oauth_token:
        logger.info("OAuth token found")
    else:
        logger.error("OAuth token not found")
        logger.error(f"Available keys: {readonly_context.state.keys()}")

    return oauth_token
