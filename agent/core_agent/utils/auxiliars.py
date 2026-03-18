from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ..config import MCPServersConfig
from .security import get_id_token


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