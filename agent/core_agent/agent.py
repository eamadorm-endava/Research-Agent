import logging
import vertexai
from vertexai import agent_engines
from google.genai.types import GenerateContentConfig, ModelArmorConfig, HttpRetryOptions
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from fastapi.openapi.models import OAuth2, OAuthFlows, OAuthFlowAuthorizationCode
from .config import GCPConfig, AgentConfig, MCPServersConfig
from .utils.security import get_id_token
 
logging.getLogger().setLevel(logging.INFO)
 
gcp_config = GCPConfig()
agent_config = AgentConfig()
mcp_servers = MCPServersConfig()
 
# Variables
project_id = gcp_config.PROJECT_ID
region = gcp_config.REGION
model_armor_template_id = f"projects/{project_id}/locations/{region}/templates/{agent_config.MODEL_ARMOR_TEMPLATE_ID}"
full_bq_mcp_server_path = mcp_servers.BIGQUERY_URL + mcp_servers.BIGQUERY_ENDPOINT
full_drive_mcp_server_path = mcp_servers.DRIVE_URL + mcp_servers.DRIVE_ENDPOINT
 
vertexai.Client(
    project=project_id,
    location=region,
)
 
# Authentication Configuration for Google Drive (Authorization Code Flow)
drive_oauth_scopes = {
    scope: "google drive access"
    for scope in mcp_servers.DRIVE_OAUTH_SCOPES.split()
    if scope.strip()
}

auth_scheme = OAuth2(
    flows=OAuthFlows(
        authorizationCode=OAuthFlowAuthorizationCode(
            authorizationUrl="https://accounts.google.com/o/oauth2/v2/auth",
            tokenUrl="https://oauth2.googleapis.com/token",
            scopes=drive_oauth_scopes,
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
tools = get_mcp_servers_tools(mcp_servers)

root_agent = Agent(
    model=Gemini(
        model_name=agent_config.MODEL_NAME,
        retry_options=agent_retry_options,
    ),
    name="research_agent",
    generate_content_config=agent_settings,
    instruction=(
        "You are a helpful research assistant with access to BigQuery data and Google Drive. "
        "You can list, read, write, update, and upload files in the user's Google Drive. "
        "IMPORTANT: If a Google Drive tool returns an error stating the user is not authenticated, "
        "it will provide a URL. You MUST provide this URL to the user and ask them to authorize "
        "access in their browser before you can continue with Drive tasks."
    ),
    tools=[
        # McpToolset(
        #     connection_params=StreamableHTTPConnectionParams(
        #         url=full_bq_mcp_server_path,
        #         timeout=mcp_servers.GENERAL_TIMEOUT,
        #     ),
        #     header_provider=lambda ctx: {
        #         "Authorization": f"Bearer {get_id_token(mcp_servers.BIGQUERY_URL)}"
        #     },
        # ),
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_drive_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            auth_scheme=auth_scheme,
            auth_credential=auth_credential,
        ),
    ],
)
 
app = agent_engines.AdkApp(agent=root_agent)