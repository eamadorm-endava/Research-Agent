from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv

import argparse

import uvicorn

from .mcp_server import create_app, mcp

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Drive MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument(
        "--log-level",
        type=str.lower,
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Logging level",
    )
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.log_level = args.log_level.upper()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
