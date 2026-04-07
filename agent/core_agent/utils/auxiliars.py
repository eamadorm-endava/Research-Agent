from fastapi.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ..config import MCPServersConfig
from .security import get_ge_oauth_token, get_id_token


def build_google_oauth_scheme(
    mcp_config: MCPServersConfig, scopes: dict[str, str]
) -> OAuth2:
    """Build the shared Google OAuth scheme used by MCP toolsets."""
    return OAuth2(
        flows=OAuthFlows(
            authorizationCode=OAuthFlowAuthorizationCode(
                authorizationUrl=mcp_config.GOOGLE_OAUTH_AUTH_URI,
                tokenUrl=mcp_config.GOOGLE_OAUTH_TOKEN_URI,
                scopes=scopes,
            )
        )
    )


def build_google_auth_credential(mcp_config: MCPServersConfig) -> AuthCredential:
    """Build the shared Google OAuth client credential used by MCP toolsets."""
    return AuthCredential(
        auth_type=AuthCredentialTypes.OAUTH2,
        oauth2=OAuth2Auth(
            client_id=mcp_config.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=mcp_config.GOOGLE_OAUTH_CLIENT_SECRET,
            redirect_uri=mcp_config.GOOGLE_OAUTH_REDIRECT_URI,
        ),
    )


def build_streamable_http_params(
    url: str, timeout: int
) -> StreamableHTTPConnectionParams:
    """Build streamable HTTP connection parameters for an MCP server."""
    return StreamableHTTPConnectionParams(url=url, timeout=timeout)


def build_runtime_headers(
    audience: str,
    readonly_context,
    auth_id: str | None = None,
) -> dict[str, str]:
    """Build runtime headers for MCP calls, including service and delegated auth."""
    headers = {"X-Serverless-Authorization": f"Bearer {get_id_token(audience)}"}
    if auth_id:
        headers["Authorization"] = (
            f"Bearer {get_ge_oauth_token(readonly_context, auth_id)}"
        )
    return headers


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

    for field_name in MCPServersConfig.model_fields:
        if not field_name.endswith("_URL"):
            continue

        server_url = getattr(mcp_config, field_name, "")
        if not server_url:
            continue

        endpoint_name = field_name.replace("_URL", "_ENDPOINT")
        endpoint = getattr(mcp_config, endpoint_name, "/mcp")
        full_server_path = f"{server_url}{endpoint}"

        tools.append(
            McpToolset(
                connection_params=build_streamable_http_params(
                    url=full_server_path,
                    timeout=mcp_config.GENERAL_TIMEOUT,
                ),
                header_provider=lambda ctx, url=server_url: {
                    "X-Serverless-Authorization": f"Bearer {get_id_token(url)}"
                },
            )
        )

    return tools
