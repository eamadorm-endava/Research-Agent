ARG UV_VERSION=0.10.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=uv_image /uv /uvx /bin/

WORKDIR /app

# NOTE: The Docker build context MUST be the root of the repository
COPY pyproject.toml uv.lock ./

RUN uv sync --group mcp_gcs --no-dev --no-install-project

# Copy the app directory to preserve module structure
COPY mcp_servers/gcs/app/ mcp_servers/gcs/app/

EXPOSE ${PORT}

CMD ["sh", "-c", "uv run --group mcp_gcs --no-sync python -m mcp_servers.gcs.app.main --host 0.0.0.0 --port ${PORT}"]


