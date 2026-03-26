import logging
import vertexai
from vertexai import agent_engines
from google.genai.types import GenerateContentConfig, ModelArmorConfig, HttpRetryOptions
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth
from fastapi.openapi.models import OAuth2, OAuthFlows, OAuthFlowAuthorizationCode

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

is_deployed = gcp_config.IS_DEPLOYED

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

agent_tools = [
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
]

if is_deployed:
    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_drive_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            header_provider=lambda ctx: {
                "X-Serverless-Authorization": f"Bearer {get_id_token(mcp_servers.DRIVE_URL)}",
                "Authorization": f"Bearer {get_ge_oauth_token(ctx, mcp_servers.GEMINI_DRIVE_AUTH_ID)}",
            },
        )
    )
else:
    auth_scheme = OAuth2(
        flows=OAuthFlows(
            authorizationCode=OAuthFlowAuthorizationCode(
                authorizationUrl=mcp_servers.DRIVE_OAUTH_AUTH_URI,
                tokenUrl=mcp_servers.DRIVE_OAUTH_TOKEN_URI,
                scopes=mcp_servers.DRIVE_OAUTH_SCOPES,
            )
        )
    )

    auth_credential = AuthCredential(
        auth_type=AuthCredentialTypes.OAUTH2,
        oauth2=OAuth2Auth(
            client_id=mcp_servers.DRIVE_OAUTH_CLIENT_ID,
            client_secret=mcp_servers.DRIVE_OAUTH_CLIENT_SECRET,
            redirect_uri=mcp_servers.DRIVE_OAUTH_REDIRECT_URI,
        ),
    )

    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_drive_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            header_provider=lambda ctx: {
                "X-Serverless-Authorization": f"Bearer {get_id_token(mcp_servers.DRIVE_URL)}"
            },
            auth_scheme=auth_scheme,
            auth_credential=auth_credential,
        )
    )

root_agent = Agent(
    model=Gemini(
        model_name=agent_config.MODEL_NAME,
        retry_options=agent_retry_options,
    ),
    name=agent_config.AGENT_NAME,
    generate_content_config=agent_settings,
    instruction=agent_config.AGENT_INSTRUCTION,
    tools=agent_tools,
)

app = agent_engines.AdkApp(agent=root_agent)
