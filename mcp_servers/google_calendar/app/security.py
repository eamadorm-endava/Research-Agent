from typing import Optional
from loguru import logger

import httpx
from google.oauth2.credentials import Credentials
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .config import CALENDAR_API_CONFIG
from .connector import EventsClient


class GoogleCalendarTokenVerifier(TokenVerifier):
    """
    Validates Google OAuth access tokens for authenticated MCP requests.
    """

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        Verifies a Google OAuth bearer token and converts it into an MCP access token.

        Args:
            token (str): The Google OAuth access token provided by the client for
                the current authenticated request.

        Returns:
            Optional[AccessToken]: A validated MCP access token or None if validation fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{CALENDAR_API_CONFIG.google_token_info_url}?access_token={token}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    token_scopes = data.get("scope", "").split()

                    # Validate that required scopes are present
                    required = set(CALENDAR_API_CONFIG.required_scopes)
                    provided = set(token_scopes)

                    if not required.issubset(provided):
                        missing = required - provided
                        logger.warning(f"Token missing required scopes: {missing}")
                        return None

                    return AccessToken(
                        token=token,
                        client_id=data.get("aud", "unknown"),
                        scopes=token_scopes,
                    )
        except Exception:
            logger.exception("Error verifying Google OAuth token")
            pass
        return None


def create_events_client() -> EventsClient:
    """Factory to create an EventsClient using the current authenticated token.

    Extracts the token from the MCP auth context and builds authorized credentials.

    Returns:
        EventsClient: An initialized client for Google Calendar and Meet.
    """
    token_obj = get_access_token()
    if not token_obj or not token_obj.token:
        raise RuntimeError("No access token provided in request context")

    # required_scopes is defined as an immutable tuple in the global config.
    # We cast it to a list here to satisfy the google.oauth2.credentials Credentials signature.
    creds = Credentials(
        token=token_obj.token, scopes=list(CALENDAR_API_CONFIG.required_scopes)
    )

    return EventsClient(creds)
