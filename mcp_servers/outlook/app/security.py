from typing import Optional
from loguru import logger

import httpx
from pydantic import SecretStr
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .outlook_client import OutlookClient


class MicrosoftTokenVerifier(TokenVerifier):
    """
    Validates Microsoft Entra ID (OAuth) access tokens for authenticated MCP requests.
    """

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        Verifies a Microsoft OAuth bearer token and converts it into an MCP access token.

        Args:
            token: str -> The Microsoft OAuth access token provided by the client for the current request.

        Returns:
            Optional[AccessToken] -> A validated MCP access token or None if validation fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Microsoft Graph API /me endpoint validates the token is live
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.get(
                    "https://graph.microsoft.com/v1.0/me", headers=headers
                )

                if resp.status_code == 200:
                    data = resp.json()
                    user_id = data.get("id", "unknown")

                    return AccessToken(
                        token=token,
                        client_id=user_id,
                        scopes=[],
                    )
                else:
                    logger.warning(
                        f"Token validation failed with Microsoft Graph API: {resp.status_code} {resp.text}"
                    )
        except Exception:
            logger.exception("Error verifying Microsoft OAuth token")
            pass
        return None


def create_outlook_client() -> OutlookClient:
    """
    Factory to create a OutlookClient using the current authenticated token.
    Extracts the token from the MCP auth context and passes it securely.

    Args:
        None

    Returns:
        OutlookClient -> An initialized client ready to interact with Graph API.
    """
    token_obj = get_access_token()
    if not token_obj or not token_obj.token:
        raise RuntimeError("No access token provided in request context")

    token_secret = SecretStr(token_obj.token)
    return OutlookClient(access_token=token_secret)
