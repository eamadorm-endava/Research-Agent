import logging

import vertexai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools import google_search
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai.types import GenerateContentConfig, HttpRetryOptions, ModelArmorConfig
from vertexai import agent_engines

from .config import AgentConfig, GCPConfig, MCPServersConfig
from .utils.security import build_mcp_headers

logging.getLogger().setLevel(logging.INFO)

# Backward-compatible fallback while the Drive MCP server is being adopted.
from .tools.drive.adk_tools import (
    drive_create_google_doc_tool,
    drive_get_file_text_tool,
    drive_list_files_tool,
    drive_search_files_tool,
    drive_upload_pdf_tool,
)


gcp_config = GCPConfig()
agent_config = AgentConfig()
mcp_servers = MCPServersConfig()

project_id = gcp_config.PROJECT_ID
region = gcp_config.REGION
model_armor_template_id = (
    f"projects/{project_id}/locations/{region}/templates/{agent_config.MODEL_ARMOR_TEMPLATE_ID}"
)
full_bq_mcp_server_path = mcp_servers.BIGQUERY_URL + mcp_servers.BIGQUERY_ENDPOINT
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


def _build_bigquery_headers(ctx):
    return build_mcp_headers(
        audience_url=mcp_servers.BIGQUERY_URL,
        call_context=ctx,
        delegated_token_header=None,
    )


def _build_drive_headers(ctx):
    return build_mcp_headers(
        audience_url=mcp_servers.DRIVE_URL,
        call_context=ctx,
        delegated_token_header=mcp_servers.DRIVE_DELEGATED_TOKEN_HEADER,
        force_disable_id_token_auth=mcp_servers.DRIVE_DISABLE_ID_TOKEN_AUTH,
    )


def _build_drive_toolset_or_fallback():
    """Use the new Drive MCP server when configured; otherwise keep the legacy in-process tools."""
    if mcp_servers.DRIVE_URL:
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_drive_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            header_provider=_build_drive_headers,
        )

    return [
        drive_list_files_tool,
        drive_search_files_tool,
        drive_get_file_text_tool,
        drive_create_google_doc_tool,
        drive_upload_pdf_tool,
    ]


_drive_tools = _build_drive_toolset_or_fallback()
if not isinstance(_drive_tools, list):
    _drive_tools = [_drive_tools]

root_agent = Agent(
    model=Gemini(
        model_name=agent_config.MODEL_NAME,
        retry_options=agent_retry_options,
    ),
    name="research_agent",
    generate_content_config=agent_settings,
    instruction=(
        "You are a helpful research assistant. "
        "You can search and read the user's Google Drive using the Drive MCP tools. "
        "When you need information from Drive, first search for relevant files, then fetch the file text. "
        "If you need to create a document or PDF in Drive, explain what you will create and proceed."
    ),
    tools=[
        google_search,
        *_drive_tools,
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=full_bq_mcp_server_path,
                timeout=mcp_servers.GENERAL_TIMEOUT,
            ),
            header_provider=_build_bigquery_headers,
        ),
    ],
)

app = agent_engines.AdkApp(agent=root_agent)
