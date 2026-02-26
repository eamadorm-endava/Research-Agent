import vertexai
from vertexai import agent_engines
from google.genai.types import GenerateContentConfig, ModelArmorConfig
from google.adk.agents import Agent
from google.adk.tools.api_registry import ApiRegistry
from .config import GCPConfig, AgentConfig

gcp_config = GCPConfig()
agent_config = AgentConfig()

project_id = gcp_config.PROJECT_ID
region = gcp_config.REGION


vertexai.Client(
        project=project_id, 
        location=region,
    )

model_armor_template_id = f"projects/{project_id}/locations/{region}/templates/{agent_config.MODEL_ARMOR_TEMPLATE_ID}"

agent_settings = GenerateContentConfig(
    temperature=agent_config.TEMPERATURE,
    top_p=agent_config.TOP_P,
    top_k=agent_config.TOP_K,
    max_output_tokens=agent_config.MAX_OUTPUT_TOKENS,
    seed=agent_config.SEED,
    model_armor_config=ModelArmorConfig(
        prompt_template_name=model_armor_template_id,
        response_template_name=model_armor_template_id,
    ),
)

# Configure with your Google Cloud Project ID and registered MCP server name
MCP_SERVER_NAME = f"projects/{project_id}/locations/global/mcpServers/google-discoveryengine.googleapis.com-mcp"

# Example header provider for BigQuery, a project header is required.
def header_provider(context):
    return {"x-goog-user-project": project_id}

# Initialize ApiRegistry
api_registry = ApiRegistry(
    api_registry_project_id=project_id,
    header_provider=header_provider
)

# Get the toolset for the specific MCP server
registry_tools = api_registry.get_toolset(
    mcp_server_name=MCP_SERVER_NAME,
    # Optionally filter tools:
    #tool_filter=["list_datasets", "run_query"]
)

root_agent = Agent(
    model=agent_config.MODEL_NAME,
    name="research_agent",
    generate_content_config=agent_settings,
    instruction="You are a helpful research assistant.",
    tools=[registry_tools]
)


app = agent_engines.AdkApp(agent=root_agent)
