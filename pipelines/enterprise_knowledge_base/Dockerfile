FROM python:3.12-slim

WORKDIR /app

# Install uv for dependency management
RUN pip install uv

# Copy project configuration and dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies globally in the system environment
RUN uv pip install --system -r pyproject.toml

# Copy the entire pipelines directory and local packages needed
COPY pipelines/ ./pipelines/
COPY mcp_servers/ ./mcp_servers/

# Expose the port for Cloud Run
EXPOSE 8080

# Run the FastAPI app using uvicorn
CMD ["uv", "run", "uvicorn", "pipelines.enterprise_knowledge_base.main:app", "--host", "0.0.0.0", "--port", "8080"]
