import logging
import vertexai
from vertexai import agent_engines
from google.adk.planners import BuiltInPlanner
from google.genai.types import (
    GenerateContentConfig,
    ModelArmorConfig,
    HttpRetryOptions,
    ThinkingConfig,
)
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth
from fastapi.openapi.models import OAuth2, OAuthFlows, OAuthFlowAuthorizationCode

from .config import GCPConfig, AgentConfig, MCPServersConfig
from .utils.security import get_id_token, get_ge_oauth_token

from pathlib import Path


from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

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


# Skills
# Load ADK Skill from directory
skills_dir = Path(__file__).parent / "skills" / "meeting-summary"
agent_skills = load_skill_from_dir(skills_dir)
meeting_summary_toolset = SkillToolset(skills=[agent_skills])

shared_google_oauth_scopes = {
    **mcp_servers.DRIVE_OAUTH_SCOPES,
    **mcp_servers.BIGQUERY_OAUTH_SCOPES,
}


def build_google_oauth_scheme(scopes: dict[str, str]) -> OAuth2:
    return OAuth2(
        flows=OAuthFlows(
            authorizationCode=OAuthFlowAuthorizationCode(
                authorizationUrl=mcp_servers.DRIVE_OAUTH_AUTH_URI,
                tokenUrl=mcp_servers.DRIVE_OAUTH_TOKEN_URI,
                scopes=scopes,
            )
        )
    )


def build_google_auth_credential() -> AuthCredential:
    return AuthCredential(
        auth_type=AuthCredentialTypes.OAUTH2,
        oauth2=OAuth2Auth(
            client_id=mcp_servers.DRIVE_OAUTH_CLIENT_ID,
            client_secret=mcp_servers.DRIVE_OAUTH_CLIENT_SECRET,
            redirect_uri=mcp_servers.DRIVE_OAUTH_REDIRECT_URI,
        ),
    )


def build_streamable_http_params(base_url: str) -> StreamableHTTPConnectionParams:
    return StreamableHTTPConnectionParams(
        url=base_url,
        timeout=mcp_servers.GENERAL_TIMEOUT,
    )


def build_runtime_headers(base_url: str, ctx, include_user_oauth: bool = False) -> dict[str, str]:
    headers = {"X-Serverless-Authorization": f"Bearer {get_id_token(base_url)}"}
    if include_user_oauth:
        headers["Authorization"] = (
            f"Bearer {get_ge_oauth_token(ctx, mcp_servers.GEMINI_DRIVE_AUTH_ID)}"
        )
    return headers


agent_tools = [meeting_summary_toolset]

if is_deployed:
    agent_tools.append(
        McpToolset(
            connection_params=build_streamable_http_params(full_bq_mcp_server_path),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.BIGQUERY_URL, ctx, include_user_oauth=True
            ),
        )
    )
else:
    shared_google_auth_scheme = build_google_oauth_scheme(shared_google_oauth_scopes)
    shared_google_auth_credential = build_google_auth_credential()
    agent_tools.append(
        McpToolset(
            connection_params=build_streamable_http_params(full_bq_mcp_server_path),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.BIGQUERY_URL, ctx
            ),
            auth_scheme=shared_google_auth_scheme,
            auth_credential=shared_google_auth_credential,
        )
    )

agent_tools.append(
    McpToolset(
        connection_params=build_streamable_http_params(full_gcs_mcp_server_path),
        header_provider=lambda ctx: build_runtime_headers(mcp_servers.GCS_URL, ctx),
    )
)

if is_deployed:
    agent_tools.append(
        McpToolset(
            connection_params=build_streamable_http_params(full_drive_mcp_server_path),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.DRIVE_URL, ctx, include_user_oauth=True
            ),
        )
    )
else:
    shared_google_auth_scheme = build_google_oauth_scheme(shared_google_oauth_scopes)
    shared_google_auth_credential = build_google_auth_credential()
    agent_tools.append(
        McpToolset(
            connection_params=build_streamable_http_params(full_drive_mcp_server_path),
            header_provider=lambda ctx: build_runtime_headers(mcp_servers.DRIVE_URL, ctx),
            auth_scheme=shared_google_auth_scheme,
            auth_credential=shared_google_auth_credential,
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
    planner=BuiltInPlanner(
        thinking_config=ThinkingConfig(
            thinking_budget=agent_config.THINKING_BUDGET,
            include_thoughts=agent_config.INCLUDE_THOUGHTS,
        )
    ),
)

app = agent_engines.AdkApp(agent=root_agent)
