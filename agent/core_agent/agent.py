import vertexai
from vertexai import agent_engines
from google.genai.types import GenerateContentConfig, ModelArmorConfig
from google.adk.agents import Agent
from google.adk.tools import google_search
from .config import GCPConfig, AgentConfig

# Custom tools
from .tools.drive.adk_tools import (
    drive_list_files_tool,
    drive_search_files_tool,
    drive_get_file_text_tool,
    drive_create_google_doc_tool,
    drive_upload_pdf_tool,
)

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

root_agent = Agent(
    model=agent_config.MODEL_NAME,
    name="research_agent",
    generate_content_config=agent_settings,
    instruction=(
        "You are a helpful research assistant. "
        "You can search and read the user's Google Drive using the Drive tools. "
        "When you need information from Drive, first search for relevant files, then fetch the file text. "
        "If you need to create a document or PDF in Drive, explain what you will create and proceed."
    ),
    tools=[
        google_search,

        # Google Drive tools
        drive_list_files_tool,
        drive_search_files_tool,
        drive_get_file_text_tool,

        # Write-back tools (require confirmation when supported)
        drive_create_google_doc_tool,
        drive_upload_pdf_tool,
    ],
)


app = agent_engines.AdkApp(agent=root_agent)
