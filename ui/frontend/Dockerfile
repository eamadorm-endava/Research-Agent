ARG UV_VERSION=0.10.7
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

FROM python:3.12-alpine AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=uv_image /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --group frontend --no-dev --no-install-project --locked
COPY ui/frontend/ ./ui/frontend/

# --- Runtime Stage ---
FROM python:3.12-alpine

WORKDIR /app

RUN adduser -D nonroot

# Remove native package managers
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip* \
           /usr/local/lib/python3.12/site-packages/setuptools* \
           /usr/local/lib/python3.12/ensurepip \
           /usr/local/bin/pip*

COPY --from=builder --chown=nonroot:nonroot /app /app
USER nonroot

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080
ENTRYPOINT ["streamlit", "run", "ui/frontend/app.py", "--server.port", "8080", "--server.address", "0.0.0.0"]
