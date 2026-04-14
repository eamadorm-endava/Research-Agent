import argparse
import sys
from loguru import logger
from .mcp_server import mcp
from .config import CALENDAR_SERVER_CONFIG

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Calendar MCP Server")
    parser.add_argument(
        "--host",
        default=CALENDAR_SERVER_CONFIG.default_host,
        help="Host interface to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=CALENDAR_SERVER_CONFIG.default_port,
        help="Port to bind to",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=CALENDAR_SERVER_CONFIG.default_log_level,
        help="Logging level",
    )
    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level

    mcp.run(transport="streamable-http")
