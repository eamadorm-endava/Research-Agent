from typing import Optional

import httpx
from loguru import logger
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from pydantic import SecretStr

from .sharepoint_client import SharePointClient


class MicrosoftTokenVerifier(TokenVerifier):
    """Validates Microsoft Entra ID access tokens for SharePoint MCP requests."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        Verifies a Microsoft OAuth bearer token against Microsoft Graph.

        Args:
            token: str -> The Microsoft OAuth access token from the current request.

        Returns:
            Optional[AccessToken] -> A validated MCP access token, or None on failure.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30.0,
                )

            if response.status_code == 200:
                user_profile = response.json()
                return AccessToken(
                    token=token,
                    client_id=user_profile.get("id", "unknown"),
                    scopes=[],
                )

            logger.warning(
                "Token validation failed with Microsoft Graph API: %s %s",
                response.status_code,
                response.text,
            )
        except Exception:
            logger.exception("Error verifying Microsoft OAuth token")
        return None


def create_sharepoint_client() -> SharePointClient:
    """
    Creates a SharePointClient with the request-scoped delegated Microsoft token.

    Args:
        None

    Returns:
        SharePointClient -> A client ready to call Microsoft Graph.
    """
    token_obj = get_access_token()
    if not token_obj or not token_obj.token:
        raise RuntimeError("No access token provided in request context")

    return SharePointClient(access_token=SecretStr(token_obj.token))
