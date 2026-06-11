import base64
import json
from typing import Optional, cast

import httpx
from loguru import logger
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .config import SHAREPOINT_API_CONFIG
from .schemas import AuthenticationError
from .sharepoint_client import SharePointClient


class SharePointTokenVerifier(TokenVerifier):
    """Validates Microsoft Graph delegated OAuth tokens for MCP requests."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Verifies a bearer token by calling Microsoft Graph and checking scopes.

        Args:
            token: str -> Delegated Microsoft Graph OAuth access token.

        Returns:
            Optional[AccessToken] -> Validated MCP access token or None when invalid.
        """
        try:
            token_scopes = _extract_token_scopes(token)
            required_scopes = {
                scope.value for scope in SHAREPOINT_API_CONFIG.required_scopes
            }
            missing_scopes = sorted(required_scopes - token_scopes)
            if missing_scopes:
                logger.warning(
                    "Microsoft Graph token missing scopes: %s", missing_scopes
                )
                return None

            async with httpx.AsyncClient(
                timeout=SHAREPOINT_API_CONFIG.request_timeout_seconds
            ) as client:
                response = await client.get(
                    f"{SHAREPOINT_API_CONFIG.graph_base_url.rstrip('/')}/me",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"$select": "id,userPrincipalName,displayName"},
                )
            if response.status_code != 200:
                logger.warning(
                    "Microsoft Graph token validation failed with status %s",
                    response.status_code,
                )
                return None

            payload = cast(dict[str, object], response.json())
            client_id = _optional_str(payload.get("id")) or "unknown"
            return AccessToken(
                token=token, client_id=client_id, scopes=sorted(token_scopes)
            )
        except Exception:
            logger.exception("Error verifying Microsoft Graph OAuth token")
            return None


def create_sharepoint_client() -> SharePointClient:
    """Creates a SharePoint client from the current MCP authorization context.

    Args:
        None -> Uses FastMCP auth context to discover the delegated bearer token.

    Returns:
        SharePointClient -> Authenticated Microsoft Graph client.
    """
    token_obj = get_access_token()
    if not token_obj or not token_obj.token:
        raise AuthenticationError("No Microsoft Graph access token provided.")
    return SharePointClient(access_token=token_obj.token)


def _extract_token_scopes(token: str) -> set[str]:
    """Extracts delegated scopes and application roles from a JWT-shaped token."""
    payload = _decode_jwt_payload(token)
    scopes = set(_optional_str(payload.get("scp") or "").split())
    roles = payload.get("roles")
    if isinstance(roles, list):
        scopes.update(str(role) for role in roles if isinstance(role, str))
    return {scope for scope in scopes if scope}


def _decode_jwt_payload(token: str) -> dict[str, object]:
    """Decodes a JWT payload without trusting it as the sole validation source."""
    segments = token.split(".")
    if len(segments) < 2:
        return {}
    payload_segment = segments[1]
    padding = "=" * (-len(payload_segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{payload_segment}{padding}")
        payload = json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}
    return cast(dict[str, object], payload) if isinstance(payload, dict) else {}


def _optional_str(value: object) -> Optional[str]:
    """Converts JSON values into optional strings."""
    return value if isinstance(value, str) else None
