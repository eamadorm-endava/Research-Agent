ARG UV_VERSION=0.10.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=uv_image /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --group mcp_sharepoint --no-dev --no-install-project --locked

COPY mcp_servers/sharepoint/app/ mcp_servers/sharepoint/app/

ENV PORT=8080
EXPOSE ${PORT}

CMD ["sh", "-c", "uv run --group mcp_sharepoint --no-sync python -m mcp_servers.sharepoint.app.main --host 0.0.0.0 --port ${PORT}"]
