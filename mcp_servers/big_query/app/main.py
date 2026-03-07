from .mcp_server import mcp

# Create ASGI application, check: https://github.com/modelcontextprotocol/python-sdk/tree/main and
# https://github.com/modelcontextprotocol/python-sdk/tree/main?tab=readme-ov-file#quickstart
# also check https://github.com/modelcontextprotocol/python-sdk/tree/main?tab=readme-ov-file#streamable-http-transport
mcp.run(transport="streamable-http")
