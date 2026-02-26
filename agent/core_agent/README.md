# Basic LLM Agent Type Creation

The main idea of this folder is to develop a basic agent that can be deployed in [Vertex AI Agent Engine](https://docs.cloud.google.com/agent-builder/agent-engine/overview) and connected to [Gemini Enterprise](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise).

The agent to be developed is an [**LLM Agent**](/docs/ADK-Intro.md#llm-agents-llmagent-agent) type.

## Folder Structure

The `core_agent/` folder follows the [ADK project structure](https://google.github.io/adk-docs/get-started/quickstart/#project-structure) and contains the following files:

- `__init__.py` -> Package initialization file, imports the agent module
- `agent.py` -> Main agent definition with LLM Agent implementation
- `config.py` -> Configuration settings for the agent
- `model_armor.py` -> Custom Model Armor implementation class
- `.env` -> Environment variables for model authentication (needed by the ADK CLI)

The .env file must be set directly inside `/core_agent` and must have the following variables:

    GOOGLE_GENAI_USE_VERTEXAI=TRUE
    GOOGLE_CLOUD_PROJECT=mock-gcp-project-id
    GOOGLE_CLOUD_LOCATION=mock-location
    PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
    REGION=${GOOGLE_CLOUD_LOCATION}
    MODEL_ARMOR_TEMPLATE_ID=mock-model-armor-template-id

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

Also, you can run the make command (make sure to be at the root of this repository):

    make run-ui-agent

## Agent Capabilities

This agent takes advantage of the [ADK tools and integrations](https://google.github.io/adk-docs/integrations/) to quickly implement required functionality. ADK provides pre-built tools for common use cases, and also supports creating custom [function-calling tools](https://google.github.io/adk-docs/tools-custom/function-tools/) for specific business needs.

### Implemented Tools

- **Google Cloud API Registry** - Dynamically exposes available Google Cloud services as Model Context Protocol (MCP) servers, allowing the agent to discover and access tools at runtime without hardcoded definitions

### Security: Model Armor Implementation

**Model Armor** is a security guardrail mechanism integrated into Vertex AI that protects agents from malicious inputs and unsafe outputs. It validates prompts and responses for harmful content, prompt injections, and jailbreak attempts.

**Two Implementation Approaches**:

#### 1. Custom Callback Class (Requires Implementation)
Implement a custom safety evaluation class using ADK [Callbacks](https://google.github.io/adk-docs/callbacks/):
- **Before Agent Callback**: Intercepts and validates user inputs before the agent processes them
- **After Agent Callback**: Validates the agent's final output before returning it to the user

This approach provides full control and customization but requires:
- Writing custom Model Armor evaluation logic (currently, a version of this can be reviewed in [`model_armor.py`](/agent/core_agent/model_armor.py))
- Handling multiple network round-trips (Python → Model Armor API → Vertex AI → Model Armor)
- Increased latency due to sequential network calls
- Setting appropriate permissions for your service account

#### 2. Native ModelArmorConfig (**Current Implementation**)
Integrate Model Armor directly into `GenerateContentConfig` at the model level:

```python
ModelArmorConfig(
    prompt_template_name=model_armor_template_id,
    response_template_name=model_armor_template_id,
)
```

**Why Choosing ModelArmorConfig**:
- **Lower Latency**: Google Cloud handles validation internally on their servers at high speed, eliminating multiple network round-trips
- **Simpler Integration**: No custom code needed - just configure template names
- **Better Performance**: Single validation within Vertex AI's infrastructure instead of callback-based validation

**How It Works**: 
- Your script sends the configuration to Vertex AI
- Vertex AI's internal Service Agent contacts Model Armor on your behalf for prompt/response sanitization
- Results are processed before and after generation

**Setup Requirement**: 
Grant the **Model Armor User** role (`roles/modelarmor.user`) to Vertex AI's internal Service Agent account:

- service-[gcp-project-number]@gcp-sa-aiplatform.iam.gserviceaccount.com 

This allows Vertex AI's backend to access and use your Model Armor templates on your behalf.
