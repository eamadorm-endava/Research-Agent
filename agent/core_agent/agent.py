import logging
from pathlib import Path

import vertexai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.adk.skills import load_skill_from_dir
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.skill_toolset import SkillToolset
from google.genai.types import (
    GenerateContentConfig,
    HttpRetryOptions,
    ModelArmorConfig,
    ThinkingConfig,
)
from vertexai import agent_engines

from .config import AgentConfig, GCPConfig, MCPServersConfig
from .utils.auxiliars import (
    build_google_auth_credential,
    build_google_oauth_scheme,
    build_runtime_headers,
)

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
full_calendar_mcp_server_path = mcp_servers.CALENDAR_URL + mcp_servers.CALENDAR_ENDPOINT

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

# Skills
# Load ADK Skill from directory
skills_dir = Path(__file__).parent / "skills" / "meeting-summary"
agent_skills = load_skill_from_dir(skills_dir)
meeting_summary_toolset = SkillToolset(skills=[agent_skills])

shared_google_oauth_scopes = {
    **mcp_servers.DRIVE_OAUTH_SCOPES,
    **mcp_servers.BIGQUERY_OAUTH_SCOPES,
    **mcp_servers.CALENDAR_OAUTH_SCOPES,
}
shared_google_auth_scheme = build_google_oauth_scheme(
    mcp_servers, shared_google_oauth_scopes
)
shared_google_auth_credential = build_google_auth_credential(mcp_servers)

agent_tools = [meeting_summary_toolset]

if is_deployed:
    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_bq_mcp_server_path,
                timeout=float(mcp_servers.GENERAL_TIMEOUT),
            ),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.BIGQUERY_URL,
                ctx,
                auth_id=mcp_servers.GEMINI_GOOGLE_AUTH_ID,
            ),
        )
    )

    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_drive_mcp_server_path,
                timeout=float(mcp_servers.GENERAL_TIMEOUT),
            ),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.DRIVE_URL,
                ctx,
                auth_id=mcp_servers.GEMINI_GOOGLE_AUTH_ID,
            ),
        )
    )

    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_calendar_mcp_server_path,
                timeout=float(mcp_servers.GENERAL_TIMEOUT),
            ),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.CALENDAR_URL,
                ctx,
                auth_id=mcp_servers.GEMINI_GOOGLE_AUTH_ID,
            ),
        )
    )
else:
    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_bq_mcp_server_path,
                timeout=float(mcp_servers.GENERAL_TIMEOUT),
            ),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.BIGQUERY_URL,
                ctx,
            ),
            auth_scheme=shared_google_auth_scheme,
            auth_credential=shared_google_auth_credential,
        )
    )

    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_drive_mcp_server_path,
                timeout=float(mcp_servers.GENERAL_TIMEOUT),
            ),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.DRIVE_URL, ctx
            ),
            auth_scheme=shared_google_auth_scheme,
            auth_credential=shared_google_auth_credential,
        )
    )

    agent_tools.append(
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_calendar_mcp_server_path,
                timeout=float(mcp_servers.GENERAL_TIMEOUT),
            ),
            header_provider=lambda ctx: build_runtime_headers(
                mcp_servers.CALENDAR_URL, ctx
            ),
            auth_scheme=shared_google_auth_scheme,
            auth_credential=shared_google_auth_credential,
        )
    )

agent_tools.append(
    McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=full_gcs_mcp_server_path, timeout=float(mcp_servers.GENERAL_TIMEOUT)
        ),
        header_provider=lambda ctx: build_runtime_headers(mcp_servers.GCS_URL, ctx),
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
