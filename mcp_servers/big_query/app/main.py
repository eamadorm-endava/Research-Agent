import argparse
from .mcp_server import mcp

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BigQuery MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    args = parser.parse_args()

    # Check https://github.com/modelcontextprotocol/python-sdk/blob/v1.26.0/src/mcp/server/fastmcp/server.py#L98
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level

    # Check https://github.com/modelcontextprotocol/python-sdk/tree/main?tab=readme-ov-file#streamable-http-transport
    mcp.run(transport="streamable-http")
