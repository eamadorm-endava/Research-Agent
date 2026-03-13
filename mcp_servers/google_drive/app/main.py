from __future__ import annotations

import argparse

import uvicorn

from .config import DRIVE_SERVER_CONFIG
from .mcp_server import create_app, mcp


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Drive MCP Server")
    parser.add_argument(
        "--host",
        default=DRIVE_SERVER_CONFIG.default_host,
        help="Host interface to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DRIVE_SERVER_CONFIG.default_port,
        help="Port to bind to",
    )
    parser.add_argument(
        "--log-level",
        type=str.lower,
        choices=["debug", "info", "warning", "error", "critical"],
        default=DRIVE_SERVER_CONFIG.default_log_level,
        help="Logging level",
    )
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level.upper()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
