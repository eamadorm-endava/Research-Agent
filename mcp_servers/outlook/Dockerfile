FROM python:3.11-slim

WORKDIR /app

# Add dependencies list later (requirements.txt or poetry)
# RUN pip install mcp httpx pydantic pydantic-settings

COPY ./app ./app

ENTRYPOINT ["python", "-m", "app.main"]
