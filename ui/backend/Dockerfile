ARG UV_VERSION=0.10.7
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=uv_image /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --only-group backend --no-dev --no-install-project --locked

# Copy backend code
COPY ui/backend/ ./ui/backend/

# Copy required modules from core_agent (token_store and config are used by UI backend routers)
COPY agent/core_agent/config/ ./agent/core_agent/config/
COPY agent/core_agent/security/token_store.py agent/core_agent/security/__init__.py ./agent/core_agent/security/

# --- Runtime Stage ---
FROM python:3.12-slim

WORKDIR /app

RUN useradd --create-home --uid 10001 nonroot

# Remove native package managers
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
ENTRYPOINT ["uvicorn", "ui.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
