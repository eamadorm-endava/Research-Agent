# Define a global ARG before the first FROM
ARG UV_VERSION=0.10.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=uv_image /uv /uvx /bin/

WORKDIR /app

# NOTE: The Docker build context MUST be the root of the repository
COPY pyproject.toml uv.lock ./

# Install only the Drive MCP server dependencies using uv
RUN uv sync --group mcp_drive --no-dev --no-install-project

# Copy the app directory to preserve module structure
COPY mcp_servers/google_drive/app/ mcp_servers/google_drive/app/

EXPOSE ${PORT}

CMD ["sh", "-c", "uv run --group mcp_drive --no-sync python -m mcp_servers.google_drive.app.main --host 0.0.0.0 --port ${PORT}"]
