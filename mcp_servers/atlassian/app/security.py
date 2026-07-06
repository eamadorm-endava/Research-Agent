from typing import Optional

import httpx
from loguru import logger
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .atlassian.client import AtlassianClient
from .config import ATLASSIAN_API_CONFIG

ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"


class AtlassianTokenVerifier(TokenVerifier):
    """Validates Atlassian OAuth 2.0 (3LO) access tokens for MCP requests."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        Verifies an Atlassian 3LO bearer token against accessible resources.

        Args:
            token: str -> The Atlassian OAuth access token from the current request.

        Returns:
            Optional[AccessToken] -> A validated MCP access token, or None on failure.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    ACCESSIBLE_RESOURCES_URL,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30.0,
                )

            if response.status_code == 200:
                resources = response.json()
                resource = select_accessible_resource(
                    resources=resources,
                    configured_cloud_id=ATLASSIAN_API_CONFIG.jira_cloud_id,
                )
                return AccessToken(
                    token=token,
                    client_id=resource.get("id", "unknown"),
                    scopes=resource.get("scopes", []),
                )

            logger.warning(
                f"Atlassian token validation failed: "
                f"{response.status_code} {response.text}"
            )
        except Exception:
            logger.exception("Error verifying Atlassian OAuth token")
        return None


def select_accessible_resource(
    resources: list[dict], configured_cloud_id: Optional[str] = None
) -> dict:
    """
    Selects the Atlassian Cloud resource that should receive API calls.

    Args:
        resources: list[dict] -> Resources returned by Atlassian accessible-resources.
        configured_cloud_id: Optional[str] -> Preferred Cloud ID configured by env.

    Returns:
        dict -> The selected accessible Atlassian resource.
    """
    if not resources:
        raise RuntimeError(
            "The Atlassian token has no accessible Jira/Confluence sites"
        )

    if configured_cloud_id:
        for resource in resources:
            if resource.get("id") == configured_cloud_id:
                return resource
        raise RuntimeError(
            f"Configured JIRA_CLOUD_ID '{configured_cloud_id}' is not "
            "accessible with the delegated token"
        )

    for resource in resources:
        scopes = resource.get("scopes", [])
        if any("jira" in scope or "confluence" in scope for scope in scopes):
            return resource

    return resources[0]


def get_accessible_resources(access_token: str) -> list[dict]:
    """
    Retrieves Atlassian Cloud resources available to the delegated token.

    Args:
        access_token: str -> Atlassian OAuth 2.0 access token.

    Returns:
        list[dict] -> Accessible resources returned by Atlassian.
    """
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            ACCESSIBLE_RESOURCES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Unable to resolve Atlassian Cloud ID: {response.status_code} {response.text}"
        )
    return response.json()


def create_atlassian_client() -> AtlassianClient:
    """
    Creates an AtlassianClient using delegated OAuth when present.

    Falls back to static API-token credentials only for legacy local runs where no
    MCP auth context exists.

    Returns:
        AtlassianClient -> A client ready to call Jira and Confluence APIs.
    """
    token_obj = get_access_token()
    if token_obj and token_obj.token:
        resources = get_accessible_resources(token_obj.token)
        resource = select_accessible_resource(
            resources=resources,
            configured_cloud_id=ATLASSIAN_API_CONFIG.jira_cloud_id,
        )
        return AtlassianClient.from_oauth(
            access_token=token_obj.token,
            instance_url=resource.get("url", "https://api.atlassian.com"),
            cloud_id=resource.get("id", ""),
        )

    creds = ATLASSIAN_API_CONFIG.credentials
    return AtlassianClient(
        email=creds.jira_user_email,
        token=creds.jira_api_token.get_secret_value(),
        instance_url=creds.jira_instance_url,
        cloud_id=creds.jira_cloud_id,
    )
