ARG UV_VERSION=0.10.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Update OS packages to patch vulnerabilities
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY --from=uv_image /uv /uvx /bin/

# Create a non-root user for execution
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

# NOTE: The Docker build context MUST be the root of the repository
COPY pyproject.toml uv.lock ./

RUN uv sync --group mcp_gcs --no-dev --no-install-project --locked

# Copy the app directory to preserve module structure
COPY mcp_servers/gcs/app/ mcp_servers/gcs/app/

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user for security (least privilege)
USER appuser

EXPOSE ${PORT}

CMD ["sh", "-c", "uv run --group mcp_gcs --no-sync python -m mcp_servers.gcs.app.main --host 0.0.0.0 --port ${PORT}"]


