# Define a global ARG before the first FROM
ARG UV_VERSION=0.10.7

# Use the predefined image layer as an alias so we can copy from it later
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

# Use a lightweight Python base image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install the required uv version using the alias
COPY --from=uv_image /uv /uvx /bin/

# Set the working directory to /app
WORKDIR /app

# NOTE: The Docker build context MUST be the root of the repository
COPY pyproject.toml uv.lock ./

# Install only the BigQuery MCP server dependencies using uv
RUN uv sync --group mcp_bq --no-dev --no-install-project

# Copy the app directory to preserve module structure
COPY mcp_servers/big_query/app/ mcp_servers/big_query/app/

# Expose port 8080
EXPOSE ${PORT}

# Run the server using uv run, in the background it uses uvicorn to run the server
CMD ["sh", "-c", "uv run --group mcp_bq --no-sync python -m mcp_servers.big_query.app.main --host 0.0.0.0 --port ${PORT}"]
