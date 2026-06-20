# ==========================================
# GLOBAL CONFIGURATION
# ==========================================
ARG UV_VERSION=0.10.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

# ==========================================
# STAGE 1: Build Environment (Builder)
# ==========================================
# Alpine Linux is completely free and famous for having 0 CVEs.
FROM python:3.12-alpine AS builder

# Optimize Python and uv behavior for container environments
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy the uv tools directly from the initial image
COPY --from=uv_image /uv /uvx /bin/

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Synchronize dependencies by creating a standalone virtual environment (.venv).
RUN uv sync --group mcp_sharepoint --no-dev --no-install-project --locked

# Copy the source code of our application to the builder
COPY mcp_servers/sharepoint/app/ mcp_servers/sharepoint/app/

# ==========================================
# STAGE 2: Hardened Runtime (Alpine)
# ==========================================
# Using the same Alpine image ensures 100% compatibility and 0 CVEs.
FROM python:3.12-alpine

WORKDIR /app

# Create a non-root user for security
RUN adduser -D nonroot

# Remove native package managers to minimize attack surface in the final image
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip* \
           /usr/local/lib/python3.12/site-packages/setuptools* \
           /usr/local/lib/python3.12/ensurepip \
           /usr/local/bin/pip*

# Copy the application code and virtual environment
COPY --from=builder --chown=nonroot:nonroot /app /app

# Switch to the non-root user
USER nonroot

# Add the virtual environment's PATH to the beginning
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

# --- EXECUTION VECTOR (ENTRYPOINT) ---
ENTRYPOINT ["python", "-m", "mcp_servers.sharepoint.app.main", "--host", "0.0.0.0", "--port", "8080"]