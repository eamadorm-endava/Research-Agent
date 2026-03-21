import logging

from fastapi.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ..config import MCPServersConfig
from .security import get_id_token


logger = logging.getLogger(__name__)


def _build_cloud_run_header_provider(server_url: str):
    def header_provider(_ctx):
        id_token = get_id_token(server_url)
        if not id_token:
            return {}
        return {"X-Serverless-Authorization": f"Bearer {id_token}"}

    return header_provider


def _build_drive_oauth_scheme(mcp_config: MCPServersConfig) -> OAuth2:
    return OAuth2(
        flows=OAuthFlows(
            authorizationCode=OAuthFlowAuthorizationCode(
                authorizationUrl=mcp_config.DRIVE_OAUTH_AUTH_URI,
                tokenUrl=mcp_config.DRIVE_OAUTH_TOKEN_URI,
                scopes=mcp_config.DRIVE_OAUTH_SCOPES,
            )
        )
    )


def _build_drive_auth_credential(mcp_config: MCPServersConfig) -> AuthCredential:
    return AuthCredential(
        auth_type=AuthCredentialTypes.OAUTH2,
        oauth2=OAuth2Auth(
            client_id=mcp_config.DRIVE_OAUTH_CLIENT_ID,
            client_secret=mcp_config.DRIVE_OAUTH_CLIENT_SECRET,
            redirect_uri=mcp_config.DRIVE_OAUTH_REDIRECT_URI,
        ),
        credential_key=mcp_config.DRIVE_OAUTH_CREDENTIAL_KEY,
    )


def get_mcp_servers_tools(mcp_config: MCPServersConfig) -> list[McpToolset]:
    """
    Scans an MCPServersConfig instance to pair server URLs
    with their respective endpoints and generates the required MCPToolset classes

    Args:
        mcp_config: An instantiated MCPServersConfig object with loaded environment variables.

    Returns:
        list[McpToolset]: A list of ready-to-use MCP tools for the agent.
    """
    tools: list[McpToolset] = []

    if mcp_config.BIGQUERY_URL:
        tools.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=f"{mcp_config.BIGQUERY_URL}{mcp_config.BIGQUERY_ENDPOINT}",
                    timeout=mcp_config.GENERAL_TIMEOUT,
                ),
                header_provider=_build_cloud_run_header_provider(
                    mcp_config.BIGQUERY_URL
                ),
            )
        )

    if mcp_config.DRIVE_URL:
        if (
            mcp_config.DRIVE_OAUTH_CLIENT_ID
            and mcp_config.DRIVE_OAUTH_CLIENT_SECRET
        ):
            tools.append(
                McpToolset(
                    connection_params=StreamableHTTPConnectionParams(
                        url=f"{mcp_config.DRIVE_URL}{mcp_config.DRIVE_ENDPOINT}",
                        timeout=mcp_config.GENERAL_TIMEOUT,
                    ),
                    auth_scheme=_build_drive_oauth_scheme(mcp_config),
                    auth_credential=_build_drive_auth_credential(mcp_config),
                    header_provider=_build_cloud_run_header_provider(
                        mcp_config.DRIVE_URL
                    ),
                )
            )
        else:
            logger.warning(
                "Skipping Google Drive MCP toolset because DRIVE_OAUTH_CLIENT_ID or "
                "DRIVE_OAUTH_CLIENT_SECRET is not configured."
            )

    if mcp_config.GCS_URL:
        tools.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=f"{mcp_config.GCS_URL}{mcp_config.GCS_ENDPOINT}",
                    timeout=mcp_config.GENERAL_TIMEOUT,
                ),
                header_provider=_build_cloud_run_header_provider(mcp_config.GCS_URL),
            )
        )

    return tools
