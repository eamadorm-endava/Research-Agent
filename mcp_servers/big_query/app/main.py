from .mcp_server import mcp

# Create ASGI application, check: https://gofastmcp.com/deployment/http#http-deployment
app = mcp.http_app()
