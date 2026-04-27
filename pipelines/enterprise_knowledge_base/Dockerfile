FROM python:3.12-slim

WORKDIR /app

# Install uv for dependency management
RUN pip install uv

# Copy project configuration and dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies globally in the system environment
RUN uv export --group classification_pipeline --group rag_pipeline --no-dev --no-hashes | uv pip install --system -r -

# Copy the necessary pipeline code
COPY pipelines/__init__.py ./pipelines/
COPY pipelines/enterprise_knowledge_base/ ./pipelines/enterprise_knowledge_base/

# Expose the port for Cloud Run
EXPOSE 8080

# Run the FastAPI app using uvicorn
CMD ["uvicorn", "pipelines.enterprise_knowledge_base.main:app", "--host", "0.0.0.0", "--port", "8080"]
