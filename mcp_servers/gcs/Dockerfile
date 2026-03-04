# Use a lightweight Python base image
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory to /app
WORKDIR /app

# NOTE: The Docker build context MUST be the root of the repository
COPY pyproject.toml uv.lock ./

# Install only the GCS MCP server dependencies using uv
RUN uv sync --group mcp_gcs --no-dev --no-install-project

# Copy the app directory
COPY mcp_servers/gcs/app/ app/

# Expose port 8080 (standard for Cloud Run)
EXPOSE 8080

# Run the FastAPI app using uv run
CMD ["uv", "run", "--group", "mcp_gcs", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]


