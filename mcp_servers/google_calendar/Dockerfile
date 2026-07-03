ARG UV_VERSION=0.10.7
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

FROM python:3.12-alpine AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=uv_image /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --group mcp_calendar --no-dev --no-install-project --locked
COPY mcp_servers/google_calendar/app/ mcp_servers/google_calendar/app/

# --- Runtime Stage ---
FROM python:3.12-alpine

WORKDIR /app

RUN adduser -D nonroot

# Remove native package managers to ensure 0 CVEs in scanners (e.g., Artifact Registry)
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip* \
           /usr/local/lib/python3.12/site-packages/setuptools* \
           /usr/local/lib/python3.12/ensurepip \
           /usr/local/bin/pip*

COPY --from=builder --chown=nonroot:nonroot /app /app
USER nonroot

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080
ENTRYPOINT ["python", "-m", "mcp_servers.google_calendar.app.main", "--host", "0.0.0.0", "--port", "8080"]
