import argparse

from .config import BIGQUERY_SERVER_CONFIG
from .mcp_server import mcp

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BigQuery MCP Server")
    parser.add_argument(
        "--host",
        default=BIGQUERY_SERVER_CONFIG.default_host,
        help="Host interface to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=BIGQUERY_SERVER_CONFIG.default_port,
        help="Port to bind to",
    )
    parser.add_argument(
        "--log-level",
        type=str.lower,
        choices=["debug", "info", "warning", "error", "critical"],
        default=BIGQUERY_SERVER_CONFIG.default_log_level,
        help="Logging level",
    )
    args = parser.parse_args()

    # Check https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/mcpserver/server.py#L126
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level.upper()

    # Check https://github.com/modelcontextprotocol/python-sdk/tree/main?tab=readme-ov-file#streamable-http-transport
    mcp.run(transport="streamable-http")
