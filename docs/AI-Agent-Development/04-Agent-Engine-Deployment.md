# Agent Engine Deployment Guide

[Agent Engine](https://docs.cloud.google.com/agent-builder/agent-engine/overview?hl=en) is a set of modular services to scale and govern agents in production; it manages end-to-end infrastructure. When deploying an agent to Agent Engine, the code runs in the *Agent Engine runtime* environment.

This document describes how to deploy the ADK agent located in the `/agent` directory to Google Cloud Vertex AI Agent Engine using a source repository.

This guide is based on the [ADK Starter Pack](https://github.com/GoogleCloudPlatform/agent-starter-pack?tab=readme-ov-file).

## Prerequisites

Before setting up the deployment, ensure you have the following ready in your Google Cloud environment:

1. **Google Cloud Project**: You must have an active GCP project (e.g., `my-project-id`).
2. **Vertex AI API Enabled**: The Vertex AI API (`aiplatform.googleapis.com`) must be enabled in your GCP project.
3. **Cloud Resource Manager API Enabled**: The Cloud Resource Manager API (`cloudresourcemanager.googleapis.com`) must be enabled.
4. **Service Account for CI/CD**: A service account with the necessary permissions to deploy to Agent Engine (e.g., Vertex AI Administrator).

## Repository Structure

The code to be deployed is located in the `/agent` directory. Here is the relevant structure:

```text
/Root
├── pyproject.toml         # Defines dependencies
├── uv.lock                # Locked dependencies (managed by uv)
└── agent/
    ├── core_agent/
    │   ├── agent.py       # Entry point defining the agent App
    │   ├── config.py      # Configuration logic
    │   └── utils/         # Helper functions (e.g. security.py)
    └── deployment/
        └── deploy.py      # Custom script for Agent Engine deployment
```

The primary entry point is `agent/core_agent/agent.py`, where the application instance is defined and exposed:

```python
# agent/core_agent/agent.py
app = agent_engines.AdkApp(agent=root_agent)
```

## Production Deployment via Source Repository

For a production environment, you should trigger the deployment securely and automatically from a CI/CD pipeline whenever code is pushed to your main branch.

### 1. Connecting the Source Repository

Connect your source repository (e.g., GitHub, GitLab, or Cloud Source Repositories) to a CI/CD platform like Google Cloud Build or GitHub Actions. In this case, CloudBuild will be used.

### 2. CI/CD Pipeline Steps

Your CI/CD pipeline should execute the following steps on every release:

1. **Checkout Code**: Clone the repository containing the source code.
2. **Setup Terraform & Infrastructure**: Provision any needed infrastructure prior to deployment.
3. **Setup Environment & Deploy Agent**: Use Python and `uv` to manage dependencies, generate the requirements file, and execute the custom deployment script (`deploy.py`).

#### Understanding the Deployment Script (`deploy.py`)

Instead of standard CLI tools, this project uses a custom deployment script `agent/deployment/deploy.py` for flexibility and programmatic configuration control prior to deployment. 

The script makes use of the [Click](https://click.palletsprojects.com/) Python package, which is a library for creating command line interfaces in a composable way with as little code as possible. It is used here to parse the numerous deployment options required by the Agent Engine API and convert them into Python variables. 

The `deploy.py` script accepts the following parameters to configure the deployment:
- `--project`, `--location`, `--service-account`: Identify the GCP environment and identity.
- `--display-name`, `--description`: Set the Agent metadata displayed in Vertex AI.
- `--source-packages`: The source directories to bundle into the container.
- `--entrypoint-module`, `--entrypoint-object`: Dictate where the main `app` instance is initialized.
- `--requirements-file`: Specifies the exact dependency requirements file to bundle.
- `--set-env-vars`: Environment variables passed into the Agent's runtime execution.
- `--min-instances`, `--max-instances`, `--cpu`, `--memory`, `--container-concurrency`, `--num-workers`: Infrastructure-level configurations mapping to the underlying Cloud Run backend.

#### Example Deployment Step (Using Cloud Build and `uv`)

Within the CI/CD pipeline, `uv` (an extremely fast Python package installer and resolver) is used to compile dependencies from the project into a `requirements.txt` file and execute the script. 

An example step in a Cloud Build configuration looks like this:

```yaml
  - name: 'python:3.12'
    id: 'deploy-agent-engine'
    entrypoint: 'sh'
    args:
      - '-c'
      - |
        # 1. Install uv for fast dependency management
        pip install uv
        
        # 2. Export dependencies to a requirements.txt file
        # This file will be bundled in the container by Vertex AI
        uv export \
          --group ai-agent \
          --no-hashes \
          --no-annotate \
          -o agent/core_agent/requirements.txt
          
        # 3. Execute the deploy.py script using uv to run it within the managed environment
        uv run --group ai-agent --group dev python -m agent.deployment.deploy \
          --project ${PROJECT_ID} \
          --location ${_REGION} \
          --display-name "${_AGENT_DISPLAY_NAME}" \
          --source-packages=./agent \
          --entrypoint-module=agent.core_agent.agent \
          --entrypoint-object=app \
          --requirements-file=./agent/core_agent/requirements.txt \
          --service-account=${_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
          --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${_REGION},MODEL_ARMOR_TEMPLATE_ID=${_MODEL_ARMOR_TEMPLATE_ID}"
```

### 3. Post-Deployment

After a successful deployment, the deployment logs will output a unique **Resource Name** for your Agent Engine deployment, which looks like this:

```text
projects/<PROJECT_NUMBER>/locations/<LOCATION_ID>/reasoningEngines/<RESOURCE_ID>
```

Keep note of the `RESOURCE_ID`. You will need it to interact with your deployed agent from client applications. 

To learn how to use and query your newly deployed agent programmatically, you can follow the [deployed_agent.ipynb](../../notebooks/deployed_agent.ipynb) notebook. Nevertheless, the main objective of this repository is to connect and interact with this agent through **Gemini Enterprise**.

## Managed Sessions and Long-Term Memory
When you deploy to Vertex AI Agent Engine, Google Cloud natively handles conversational context, session state, and long-term memory for your agent without requiring custom database backends (like Redis or PostgreSQL).

* **Fully Managed Sessions**: The `VertexAiSessionService` is automatically provisioned and utilized. Any `Session` state or interactions you have over a conversation are automatically persisted and managed by Vertex AI.
* **Long-Term Knowledge (Memory Bank)**: Vertex AI provides [Memory Bank](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/overview), an advanced storage solution that automatically processes, consolidates, and persists conversation histories as searchable memories. Connected agents can look up past conversations across sessions using the `VertexAiMemoryBankService`.

Using these built-in services offloads infrastructure management and data persistence, allowing you to focus purely on configuring the agent logic.
