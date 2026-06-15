import argparse
from .mcp_server import mcp
from .config import ONEDRIVE_SERVER_CONFIG

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OneDrive MCP Server")
    parser.add_argument(
        "--host",
        default=ONEDRIVE_SERVER_CONFIG.default_host,
        help="Host interface to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=ONEDRIVE_SERVER_CONFIG.default_port,
        help="Port to bind to",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=ONEDRIVE_SERVER_CONFIG.default_log_level.upper(),
        help="Logging level",
    )
    args = parser.parse_args()

    # Check https://github.com/modelcontextprotocol/python-sdk/blob/v1.26.0/src/mcp/server/fastmcp/server.py#L98
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level

    # Check https://github.com/modelcontextprotocol/python-sdk/tree/main?tab=readme-ov-file#streamable-http-transport
    mcp.run(transport="streamable-http")
