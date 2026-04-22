# Agent Engine Deployment Guide

[Vertex AI Agent Engine](https://docs.cloud.google.com/agent-builder/agent-engine/overview?hl=en) manages the end-to-end infrastructure to scale and govern agents in production. This guide details how to deploy the ADK agent (located in `/agent`) using a source repository.

This guide is based on the [ADK Starter Pack](https://github.com/GoogleCloudPlatform/agent-starter-pack?tab=readme-ov-file).

## Prerequisites

1. **Active GCP Project** with Billing enabled.
2. **APIs Enabled**: Vertex AI API (`aiplatform.googleapis.com`) and Cloud Resource Manager API (`cloudresourcemanager.googleapis.com`).
3. **CI/CD Service Account**: Access to deploy Agent Engine resources (e.g., Vertex AI Administrator).

## Repository Structure

The deployable code is housed in `/agent`:

```text
/Root
├── pyproject.toml         # Defines dependencies
├── uv.lock                # Locked dependencies (managed by uv)
└── agent/
    ├── core_agent/
    │   ├── agent.py       # Entry point defining the `app` instance
    │   ├── config.py      # Configuration logic
    │   └── utils/         
    └── deployment/
        └── deploy.py      # Custom script for Agent Engine deployment
```

> **Entry Point**: The deployment expects an application instance. In `agent/core_agent/agent.py`, the entry point is exposed as `app = agent_engines.AdkApp(agent=root_agent)`.

## Production Deployment via CI/CD

For production, trigger the deployment securely from a CI/CD pipeline (like Google Cloud Build).

### 1. The Deployment Script (`deploy.py`)

Instead of standard CLI tools, this project uses `agent/deployment/deploy.py` for programmatic control. It uses the `Click` package to map parameters to the Agent Engine API:

*   **Identity & Location**: `--project`, `--location`, `--service-account`
*   **Metadata**: `--display-name`, `--description`
*   **Source Code**: `--source-packages`, `--entrypoint-module`, `--entrypoint-object`
*   **Environment**: `--requirements-file`, `--set-env-vars`
*   **Scaling**: `--min-instances`, `--max-instances`, `--cpu`, `--memory`

### 2. Example Cloud Build Step

The pipeline uses `uv` to rapidly export dependencies and execute the deployment script. 

```yaml
  - name: 'python:3.12'
    id: 'deploy-agent-engine'
    entrypoint: 'sh'
    args:
      - '-c'
      - |
        pip install uv
        
        # 1. Export dependencies for Vertex AI
        uv export --group ai-agent --no-hashes --no-annotate -o agent/core_agent/requirements.txt
          
        # 2. Execute deployment securely
        uv run --group ai-agent --group dev python -m agent.deployment.deploy \
          --project ${PROJECT_ID} \
          --location ${_REGION} \
          --display-name "${_AGENT_DISPLAY_NAME}" \
          --source-packages=./agent \
          --entrypoint-module=agent.core_agent.agent \
          --entrypoint-object=app \
          --requirements-file=./agent/core_agent/requirements.txt \
          --requirements-file=./agent/core_agent/requirements.txt \
          --service-account=${_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
          --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${_REGION},DRIVE_URL=${_DRIVE_URL},GEMINI_GOOGLE_AUTH_ID=$$GOOGLE_AUTH_ID"
```

### 3. Post-Deployment

Upon success, a unique **Resource Name** is generated:
`projects/<PROJECT_NUMBER>/locations/<LOCATION_ID>/reasoningEngines/<RESOURCE_ID>`

Keep note of this `RESOURCE_ID`. It is required to bind the agent to Gemini Enterprise.

---

## Managed Sessions and Long-Term Memory

By deploying to Vertex AI Agent Engine, Google Cloud natively handles contextual state without requiring custom databases (like Redis or PostgreSQL).

*   **Fully Managed Sessions**: Through `VertexAiSessionService`, conversation state is automatically persisted and managed by Vertex AI.
*   **Long-Term Knowledge (Memory Bank)**: Vertex AI's [Memory Bank](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/overview) automatically consolidates conversation histories into searchable memories. Connected agents look up past interactions via `VertexAiMemoryBankService`.
