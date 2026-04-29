import base64
import json
from typing import Optional

from loguru import logger

import google.auth
import google.oauth2.id_token
from google.auth.transport.requests import Request
from google.adk.agents.readonly_context import ReadonlyContext


def get_id_token(audience: str) -> Optional[str]:
    """Generates a valid ID token for calling GCP-authenticated services such as Cloud Run.

    Tries the GCP metadata server first, then falls back to local ADC credentials for development.

    Args:
        audience: str -> The target service URL used as the token audience.

    Returns:
        Optional[str] -> The ID token string, or None if retrieval fails via both paths.
    """
    logger.info(f"Generating ID token for audience: {audience}")
    request = Request()
    try:
        logger.debug(
            f"Retrieving ID token from metadata server for audience {audience}"
        )
        id_token = google.oauth2.id_token.fetch_id_token(request, audience)
        logger.debug("ID token successfully retrieved from metadata server")
        return id_token
    except Exception as exc:
        logger.warning(f"Metadata-server ID token retrieval failed: {exc}")

    try:
        logger.debug("Retrieving ID token from local ADC credentials")
        credentials, _ = google.auth.default()
        credentials.refresh(request)
        id_token = getattr(credentials, "id_token", None)
        if id_token:
            logger.debug("ID token retrieved from local ADC credentials")
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


def extract_user_email_from_token(token: str) -> Optional[str]:
    """Decodes the JWT payload from a Gemini Enterprise OAuth token to extract the user email.

    Performs base64url decoding of the JWT middle segment without signature verification,
    relying solely on the token already being trusted (injected by GE into session state).

    Args:
        token: str -> The JWT-formatted OAuth token string.

    Returns:
        Optional[str] -> The email claim from the payload, or None if unavailable.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            logger.debug(
                f"Token is not JWT-formatted (found {len(parts)} segments). "
                f"It appears to be an opaque Access Token. "
                f"Token prefix: {token[:10]}..."
            )
            return None
        padding = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        email = payload.get("email")
        if email:
            logger.debug(f"Extracted GE user email from token payload: {email}")
        return email
    except Exception as exc:
        logger.warning(f"Failed to decode OAuth token for email extraction: {exc}")
        return None
