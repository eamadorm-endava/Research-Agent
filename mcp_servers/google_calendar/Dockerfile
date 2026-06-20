# Define a global ARG before the first FROM
ARG UV_VERSION=0.10.7

# Use the predefined image layer as an alias so we can copy from it later
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_image

# Use a lightweight Python base image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Update OS packages to patch vulnerabilities
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Install the required uv version using the alias
COPY --from=uv_image /uv /uvx /bin/

# Create a non-root user for execution
RUN useradd -m -s /bin/bash appuser

# Set the working directory to /app
WORKDIR /app

# NOTE: The Docker build context MUST be the root of the repository
COPY pyproject.toml uv.lock ./

# Install only the Calendar MCP server dependencies using uv
RUN uv sync --group mcp_calendar --no-dev --no-install-project --locked

# Copy the app directory to preserve module structure
COPY mcp_servers/google_calendar/app/ mcp_servers/google_calendar/app/

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user for security (least privilege)
USER appuser

# Expose port 8080 (CloudRun default port)
ENV PORT=8080
EXPOSE ${PORT}

# Run the server using uv run
CMD ["sh", "-c", "uv run --group mcp_calendar --no-sync python -m mcp_servers.google_calendar.app.main --host 0.0.0.0 --port ${PORT}"]
