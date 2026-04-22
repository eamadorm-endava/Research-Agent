import argparse

from .config import GCS_SERVER_CONFIG
from .mcp_server import mcp

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCS MCP Server")
    parser.add_argument(
        "--host",
        default=GCS_SERVER_CONFIG.default_host,
        help="Host interface to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=GCS_SERVER_CONFIG.default_port,
        help="Port to bind to",
    )
    parser.add_argument(
        "--log-level",
        type=str.lower,
        choices=["debug", "info", "warning", "error", "critical"],
        default=GCS_SERVER_CONFIG.default_log_level,
        help="Logging level",
    )
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level.upper()

    mcp.run(transport="streamable-http")
