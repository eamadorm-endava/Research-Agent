# Use a lightweight Python base image
FROM python:3.12-slim

ENV UV_VERSION=0.10.7

# Copy pyproject.toml and uv.lock in the working directory
COPY pyproject.toml uv.lock ./

# Upgrade pip and install the required uv version
RUN pip install --upgrade pip &&\
    pip install uv==${UV_VERSION}

# Set the working directory to /app
WORKDIR /app

# NOTE: The Docker build context MUST be the root of the repository
COPY pyproject.toml uv.lock ./

# Install only the BigQuery MCP server dependencies using uv
RUN uv sync --group mcp_bq --no-dev --no-install-project

# Copy the app directory to preserve module structure
COPY mcp_servers/big_query/app/ mcp_servers/big_query/app/

# Expose port 8080
EXPOSE 8080

# Run the FastAPI app using uv run
CMD [
    "sh", 
    "-c", 
    "uv run --group mcp_bq python -m mcp_servers.big_query.app.main --host 0.0.0.0 --port ${PORT:-8080}"
]
