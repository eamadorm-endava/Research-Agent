from fastapi.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.agents.readonly_context import ReadonlyContext

from ..config import MCPServersConfig
from .security import get_ge_oauth_token, get_id_token


def build_google_oauth_scheme(
    mcp_config: MCPServersConfig, scopes: dict[str, str]
) -> OAuth2:
    """
    Builds the shared Google OAuth scheme for MCP toolsets.

    Args:
        mcp_config: The MCP server configuration with Google OAuth settings.
        scopes: The OAuth scopes to request.

    Returns:
        OAuth2: The configured OAuth2 scheme.
    """
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
    """
    Builds the shared Google OAuth credential for MCP toolsets.

    Args:
        mcp_config: The MCP server configuration with Google OAuth client settings.

    Returns:
        AuthCredential: The configured OAuth credential.
    """
    return AuthCredential(
        auth_type=AuthCredentialTypes.OAUTH2,
        oauth2=OAuth2Auth(
            client_id=mcp_config.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=mcp_config.GOOGLE_OAUTH_CLIENT_SECRET,
            redirect_uri=mcp_config.GOOGLE_OAUTH_REDIRECT_URI,
        ),
    )


def build_runtime_headers(
    audience: str,
    readonly_context: ReadonlyContext,
    auth_id: str | None = None,
) -> dict[str, str]:
    """
    Builds the runtime headers for MCP requests.

    Args:
        audience (str): The target audience used to generate the ID token.
        readonly_context (ReadonlyContext): The runtime context used to get the delegated token.
        auth_id (str | None): The auth resource ID used to fetch the delegated user token.

    Returns:
        dict[str, str]: The headers for the MCP request.
    """
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
                connection_params=StreamableHTTPConnectionParams(
                    url=full_server_path,
                    timeout=mcp_config.GENERAL_TIMEOUT,
                ),
                header_provider=lambda ctx, url=server_url: {
                    "X-Serverless-Authorization": f"Bearer {get_id_token(url)}"
                },
            )
        )

    return tools
