import logging
import vertexai
from vertexai import agent_engines
from google.genai.types import GenerateContentConfig, ModelArmorConfig, HttpRetryOptions
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from .config import GCPConfig, AgentConfig, MCPServersConfig
from .utils.security import get_id_token, get_ge_oauth_token

logging.getLogger().setLevel(logging.INFO)

gcp_config = GCPConfig()
agent_config = AgentConfig()
mcp_servers = MCPServersConfig()

# Variables
project_id = gcp_config.PROJECT_ID
region = gcp_config.REGION
model_armor_template_id = f"projects/{project_id}/locations/{region}/templates/{agent_config.MODEL_ARMOR_TEMPLATE_ID}"
full_bq_mcp_server_path = mcp_servers.BIGQUERY_URL + mcp_servers.BIGQUERY_ENDPOINT
full_gcs_mcp_server_path = mcp_servers.GCS_URL + mcp_servers.GCS_ENDPOINT
full_drive_mcp_server_path = mcp_servers.DRIVE_URL + mcp_servers.DRIVE_ENDPOINT

vertexai.Client(
    project=project_id,
    location=region,
)

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

agent_retry_options = HttpRetryOptions(
    attempts=agent_config.RETRY_ATTEMPTS,
    initial_delay=agent_config.RETRY_INITIAL_DELAY,
    exp_base=agent_config.RETRY_EXP_BASE,
    max_delay=agent_config.RETRY_MAX_DELAY,
)

# MCP toolset construction is centralized in utils/auxiliars.py:get_mcp_servers_tools
# tools = get_mcp_servers_tools(mcp_servers)

root_agent = Agent(
    model=Gemini(
        model_name=agent_config.MODEL_NAME,
        retry_options=agent_retry_options,
    ),
    name=agent_config.AGENT_NAME,
    generate_content_config=agent_settings,
    instruction=agent_config.AGENT_INSTRUCTION,
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_bq_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            header_provider=lambda ctx: {
                "X-Serverless-Authorization": f"Bearer {get_id_token(mcp_servers.BIGQUERY_URL)}"
            },
        ),
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_gcs_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            header_provider=lambda ctx: {
                "X-Serverless-Authorization": f"Bearer {get_id_token(mcp_servers.GCS_URL)}"
            },
        ),
        # Uncomment the following lines when Google Drive MCP server is deployed, this will avoid deploying the agent
        # and failing to start
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_drive_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            header_provider=lambda ctx: {
                "X-Serverless-Authorization": f"Bearer {get_id_token(mcp_servers.DRIVE_URL)}",
                "Authorization": f"Bearer {get_ge_oauth_token(ctx, mcp_servers.GEMINI_DRIVE_AUTH_ID)}",
            },
        ),
    ],
)

app = agent_engines.AdkApp(agent=root_agent)
