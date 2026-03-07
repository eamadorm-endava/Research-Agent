from .mcp_server import mcp

# Create ASGI application, check: https://github.com/modelcontextprotocol/python-sdk/tree/main
app = mcp.streamable_http_app()
