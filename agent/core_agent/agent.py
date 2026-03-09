import vertexai
from vertexai import agent_engines
from google.genai.types import GenerateContentConfig, ModelArmorConfig
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from .config import GCPConfig, AgentConfig, MCPServersConfig

gcp_config = GCPConfig()
agent_config = AgentConfig()
mcp_servers = MCPServersConfig()

project_id = gcp_config.PROJECT_ID
region = gcp_config.REGION


vertexai.Client(
    project=project_id,
    location=region,
)

model_armor_template_id = f"projects/{project_id}/locations/{region}/templates/{agent_config.MODEL_ARMOR_TEMPLATE_ID}"

full_bq_mcp_server_path = mcp_servers.BIGQUERY_URL + mcp_servers.BIGQUERY_ENDPOINT

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

agent_retry_options = types.HttpRetryOptions(
    attempts=agent_config.RETRY_ATTEMPTS,
    initial_delay=agent_config.RETRY_INITIAL_DELAY,
    exp_base=agent_config.RETRY_EXP_BASE,
    max_delay=agent_config.RETRY_MAX_DELAY,
)

token = "mock-token-id"

# Check https://google.github.io/adk-docs/tools-custom/mcp-tools/#pattern-2-remote-mcp-servers-streamable-http to learn how to connect
# and also https://github.com/google/adk-python/blob/327b3affd2d0a192f5a072b90fdb4aae7575be90/src/google/adk/tools/mcp_tool/mcp_session_manager.py#L113
root_agent = Agent(
    model=Gemini(
        model_name=agent_config.MODEL_NAME,
        retry_options=agent_retry_options,
    ),
    name="research_agent",
    generate_content_config=agent_settings,
    instruction="You are a helpful research assistant.",
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=f"{full_bq_mcp_server_path}",
                headers={"Authorization": f"Bearer {token}"},
            ),
        ),
    ],
)


app = agent_engines.AdkApp(agent=root_agent)
