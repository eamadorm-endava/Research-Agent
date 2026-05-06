import time
import threading
from datetime import datetime
from typing import Optional

from loguru import logger

import google.auth
import google.oauth2.id_token
from google.auth import jwt
from google.auth.transport.requests import Request
from google.adk.agents.readonly_context import ReadonlyContext


# Global cache for ID tokens: {audience: (token, expiry_timestamp)}
_ID_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_LOCK = threading.Lock()
DEFAULT_TTL = 3000  # Fallback TTL


def get_id_token(audience: str) -> Optional[str]:
    """Generates or retrieves a cached ID token for calling GCP-authenticated services.

    Args:
        audience: str -> The target service URL used as the token audience.

    Returns:
        Optional[str] -> The ID token string, or None if retrieval fails.
    """
    now = time.time()

    with _CACHE_LOCK:
        # Check cache first
        if audience in _ID_TOKEN_CACHE:
            token, expiry = _ID_TOKEN_CACHE[audience]
            if expiry > now + 30:  # 30 second buffer
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

        # Decode to get real expiry
        try:
            payload = jwt.decode(id_token, verify=False)
            expiry = float(payload.get("exp", now + DEFAULT_TTL))
            logger.debug(f"Token expiry from JWT: {expiry} (in {expiry - now:.0f}s)")
        except Exception:
            expiry = now + DEFAULT_TTL

        with _CACHE_LOCK:
            _ID_TOKEN_CACHE[audience] = (id_token, expiry)

        logger.debug("ID token successfully retrieved from metadata server and cached")
        return id_token
    except Exception as exc:
        logger.warning(f"Metadata-server ID token retrieval failed: {exc}")

    # Path 2: Local ADC (Development)
    try:
        with _CACHE_LOCK:
            # Double-check cache inside lock to avoid race condition
            if audience in _ID_TOKEN_CACHE:
                cached_token, expiry = _ID_TOKEN_CACHE[audience]
                if expiry > now + 10:
                    return cached_token

            logger.debug(f"Refreshing local ADC credentials for audience: {audience}")
            credentials, _ = google.auth.default()
            credentials.refresh(request)
            id_token = getattr(credentials, "id_token", None)

            if id_token:
                try:
                    payload = jwt.decode(id_token, verify=False)
                    expiry = float(payload.get("exp", now + 60))
                    expiry_dt = datetime.fromtimestamp(expiry).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    token_aud = payload.get("aud")
                    logger.debug(f"ADC Token aud: {token_aud}, exp: {expiry_dt}")
                except Exception:
                    expiry = now + 60

                _ID_TOKEN_CACHE[audience] = (id_token, expiry)
                return id_token

        logger.warning("ADC credentials did not yield an ID token")
    except Exception as exc:
        logger.warning(f"Unable to obtain ID token from local ADC credentials: {exc}")

    return None


def clear_id_token_cache() -> None:
    """Clears the global ID token cache. Primarily used for testing."""
    with _CACHE_LOCK:
        _ID_TOKEN_CACHE.clear()
        logger.debug("ID token cache cleared")


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
