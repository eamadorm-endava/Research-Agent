from fastapi import FastAPI, Request
from mcp.server.sse import SseServerTransport
from app.mcp_server import mcp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GCS MCP Server",
    description="MCP Server for Google Cloud Storage with SSE transport",
    version="0.1.0"
)

sse_transport = SseServerTransport("/messages")

@app.get("/")
async def root():
    return {"message": "GCS MCP Server is running", "sse_endpoint": "/sse", "messages_endpoint": "/messages"}

@app.get("/sse")
async def sse(request: Request):
    """
    Establish an SSE connection for the MCP protocol.
    """
    logger.info("New SSE connection request")
    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as sse:
        await mcp.run(
            request.scope,
            request.receive,
            sse.send,
            mcp.create_initialization_options()
        )

@app.post("/messages")
async def messages(request: Request):
    """
    Handle incoming JSON-RPC messages from the client.
    """
    logger.info("New message received")
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)
