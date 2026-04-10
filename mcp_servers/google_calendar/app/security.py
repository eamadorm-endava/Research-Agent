import logging
from typing import Optional, Sequence

import httpx
from google.oauth2.credentials import Credentials
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .config import CALENDAR_API_CONFIG
from .connector import EventsClient

logger = logging.getLogger(__name__)


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


def create_events_client(*, scopes: Optional[Sequence[str]] = None) -> EventsClient:
    """Factory to create an EventsClient using the current authenticated token.

    Extracts the token from the MCP auth context and builds authorized credentials.

    Args:
        scopes (Optional[Sequence[str]]): Optional specific scopes for the client.

    Returns:
        EventsClient: An initialized client for Google Calendar and Meet.
    """
    token_obj = get_access_token()
    if not token_obj or not token_obj.token:
        raise RuntimeError("No access token provided in request context")

    creds = Credentials(token=token_obj.token, scopes=scopes)

    return EventsClient(creds)
