"""Entry point for the Atlassian MCP Server."""

import argparse
import sys
from loguru import logger

from .mcp_server import mcp
from .config import ATLASSIAN_SERVER_CONFIG


def main() -> None:
    """Parses command line arguments and runs the FastMCP server.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Atlassian MCP Server")
    parser.add_argument(
        "--host",
        default=ATLASSIAN_SERVER_CONFIG.default_host,
        help="Host interface to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=ATLASSIAN_SERVER_CONFIG.default_port,
        help="Port to bind to",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=ATLASSIAN_SERVER_CONFIG.default_log_level,
        help="Logging level",
    )
    parser.add_argument(
        "--transport",
        default="streamable-http",
        choices=["streamable-http", "stdio"],
        help="MCP transport protocol to use",
    )
    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level

    logger.info(f"Starting Atlassian MCP Server using transport: {args.transport}")
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
