from unittest.mock import patch

# Mock vertexai.Client at module level before importing the agent to prevent real GCP API initialization
with patch("vertexai.Client"):
    from agent.core_agent.agent import research_agent

from google.adk.tools.mcp_tool import McpToolset


def test_research_agent_mounts_atlassian_mcp_server():
    """Verify that the built research_agent has successfully mounted the Atlassian MCP server."""
    atlassian_mcp = None
    for tool in research_agent.tools:
        if isinstance(tool, McpToolset):
            if "8085" in tool._connection_params.url:
                atlassian_mcp = tool
                break

    assert atlassian_mcp is not None, (
        "Atlassian MCP Toolset was not found in research_agent's registered tools list."
    )
    assert atlassian_mcp._connection_params.url == "http://localhost:8085/mcp"
    assert atlassian_mcp._connection_params.timeout == 60.0
