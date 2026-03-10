# Agent Engine Deployment Guide

[Agent Engine](https://docs.cloud.google.com/agent-builder/agent-engine/overview?hl=en) is a set of modular services that help developers scale and govern agents in production; it manages end-to-end infrastructure. When deploying an agent to Agent Engine, the code runs in the *Agent Engine runtime* environment.

This document describes how to deploy the ADK agent located in the `/agent` directory to Google Cloud Vertex AI Agent Engine using a source repository. This approach mimics a production-grade deployment, relying on version control and CI/CD pipelines (such as GitHub Actions or Cloud Build) rather than deploying locally from a developer's machine.

## Prerequisites

Before setting up the deployment, ensure you have the following ready in your Google Cloud environment:

1. **Google Cloud Project**: You must have an active GCP project (e.g., `my-project-id`).
2. **Vertex AI API Enabled**: The Vertex AI API (`aiplatform.googleapis.com`) must be enabled in your GCP project.
3. **Cloud Resource Manager API Enabled**: The Cloud Resource Manager API (`cloudresourcemanager.googleapis.com`) must be enabled.
4. **Service Account for CI/CD**: A service account with the necessary permissions to deploy to Agent Engine (e.g., Vertex AI Administrator).

## Repository Structure

The code to be deployed is located in the `/agent` directory. Here is the relevant structure:

```text
/Research-Agent
├── pyproject.toml         # Defines dependencies: google-cloud-aiplatform[adk,agent-engines]
└── agent/
    ├── core_agent/
    │   ├── agent.py       # Entry point defining the agent App
    │   └── config.py      # Configuration logic
    └── tools/             # Custom tools for the agent
```

The primary entry point is `agent/core_agent/agent.py`, where the application instance is defined and exposed:

```python
# agent/core_agent/agent.py
app = agent_engines.AdkApp(agent=root_agent)
```

## Production Deployment via Source Repository

For a production environment, you should trigger the deployment securely and automatically from a CI/CD pipeline whenever code is pushed to your main branch.

### 1. Connecting the Source Repository

Connect your source repository (e.g., GitHub, GitLab, or Cloud Source Repositories) to a CI/CD platform like Google Cloud Build or GitHub Actions. 

### 2. Configure Service Account Authentication

In your CI/CD pipeline, authenticate using Workload Identity Federation or a Service Account JSON key. This grants the pipeline permission to deploy resources to your Google Cloud project.

### 3. CI/CD Pipeline Steps

Your CI/CD pipeline should execute the following steps on every release:

1. **Checkout Code**: Clone the repository containing the `/agent` directory.
2. **Setup Environment**: Install Python and the `adk` CLI tool.
3. **Authenticate**: Authenticate with Google Cloud using your Service Account.
4. **Deploy**: Run the `adk deploy agent_engine` command targeting the `agent` directory.

#### Example Deployment Step (Shell Script)

```shell
export PROJECT_ID="your-gcp-project-id"
export LOCATION_ID="us-central1"

# The command packages the /agent folder into a container and deploys it
adk deploy agent_engine \
  --project=$PROJECT_ID \
  --region=$LOCATION_ID \
  --display_name="Production Research Agent" \
  agent
```

*Note: You must run this command from the root of the repository so that the `agent` positional argument correctly targets the `/agent` directory.*

### 4. Post-Deployment

After a successful deployment, the deployment logs will output a unique **Resource Name** for your Agent Engine deployment, which looks like this:

```text
projects/<PROJECT_NUMBER>/locations/<LOCATION_ID>/reasoningEngines/<RESOURCE_ID>
```

Keep note of the `RESOURCE_ID`. You will need it to interact with your deployed agent from client applications.

## Using the Deployed Agent

Once deployed, you can interact with your agent running on Agent Engine using various methods, including the Vertex AI Python SDK.

```python
import vertexai
from vertexai import agent_engines

project_id = "your-gcp-project-id"
location = "us-central1"
resource_id = "YOUR_RESOURCE_ID"  # Found in deployment logs

vertexai.init(project=project_id, location=location)

# Get the deployed reasoning engine
agent_engine = agent_engines.get(
    f"projects/{project_id}/locations/{location}/reasoningEngines/{resource_id}"
)

# Query the remote agent
response = agent_engine.query(
    input="Research the latest advancements in quantum computing."
)
print(response)
```
