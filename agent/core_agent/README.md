# Basic LLM Agent Type Creation

The main idea of this folder is to develop a basic agent that can be deployed in [Vertex AI Agent Engine](https://docs.cloud.google.com/agent-builder/agent-engine/overview), and connected with [Gemini Enterprise](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise).

The agent to be developed is an [**LLM Agent**](/docs/ADK-Intro.md#llm-agents-llmagent-agent) type.

## Folder Structure

The `core_agent/` folder follows the [ADK project structure](https://google.github.io/adk-docs/get-started/quickstart/#project-structure) and contains the following files:

- `__init__.py` -> Package initialization file, imports the agent module
- `agent.py` -> Main agent definition with LLM Agent implementation
- `config.py` -> Configuration settings for the agent
- `.env` -> Environment variables for model authentication (needed by the ADK CLI)

The .env file must be set directly inside `/core_agent` and must have the following variables:

    GOOGLE_GENAI_USE_VERTEXAI=TRUE
    GOOGLE_CLOUD_PROJECT=mock-gcp-project-id
    GOOGLE_CLOUD_LOCATION=mock-location

## How to test the Agent Locally

There are [three ways](https://google.github.io/adk-docs/get-started/quickstart/#run-your-agent) to test the agent, here it is explained how to test it using the **Dev UI**

### 1. Authenticate in GCP 

As the project uses Vertex AI to connect with Gemini models, it is required to previously authenticate with Google Cloud using the gcloud CLI.

To do so, open the terminal and run:

    gcloud auth application default login --project mock-gcp-project-id
    gcloud config set project mock-gcp-project-id

Or you can run the make command (the terminal must be at the root of this repository):

    make gcloud-auth

### 2. Execute the ADK CLI comand

As ADK was installed using uv, it is needed to execute the command inside uv.

Open the terminal in the `agent/` folder, and run:

    uv run adk web --port 8000

Also, you can also run the make command (make sure to be at the root of this repository):

    make run-ui-agent

## Agent Capabilities

This agent takes advantage of the [ADK tools and integrations](https://google.github.io/adk-docs/integrations/) to quickly implement required functionality. ADK provides pre-built tools for common use cases, and also supports creating custom [function-calling tools](https://google.github.io/adk-docs/tools-custom/function-tools/) for specific business needs.

### Implemented Tools

- **Google Cloud API Registry** - Dynamically exposes available Google Cloud services as Model Context Protocol (MCP) servers, allowing the agent to discover and access tools at runtime without hardcoded definitions

### Security: Model Armor Implementation

**Model Armor** is a security guardrail mechanism designed to protect agents from malicious inputs and unsafe outputs. It validates:

- User inputs for prompt injections and jailbreak attempts
- Agent outputs for harmful or inappropriate content
- Tool execution safety and policy compliance

**Implementation Strategy**: Model Armor will be implemented using ADK [Before Agent and After Agent Callbacks](https://google.github.io/adk-docs/callbacks/):

- **Before Agent Callback**: Validates incoming user messages before the agent processes them, checking for prompt injections and unsafe inputs
- **After Agent Callback**: Validates the agent's final output before returning it to the user, ensuring content safety and policy compliance

This callback-based approach provides a clean, non-invasive way to enforce security policies without modifying the core agent logic. For more information on callbacks and security best practices, see the [ADK Callbacks documentation](https://google.github.io/adk-docs/callbacks/) and [Safety and Security guide](https://google.github.io/adk-docs/safety/). 