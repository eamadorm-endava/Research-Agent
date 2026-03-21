import logging
import vertexai
from vertexai import agent_engines
from google.genai.types import GenerateContentConfig, ModelArmorConfig, HttpRetryOptions
from google.adk.agents import Agent
from google.adk.models import Gemini

from .config import GCPConfig, AgentConfig, MCPServersConfig
from .debug_plugin import CloudLoggingDebugPlugin
from .utils.auxiliars import get_mcp_servers_tools

logging.getLogger().setLevel(logging.INFO)

gcp_config = GCPConfig()
agent_config = AgentConfig()
mcp_servers = MCPServersConfig()


def _build_debug_plugins(config: AgentConfig) -> list[CloudLoggingDebugPlugin]:
    if not config.ENABLE_DEBUG_LOGGING:
        return []

    logging.getLogger("google_adk").setLevel(logging.DEBUG)
    logging.getLogger("google_adk.google.adk.models.google_llm").setLevel(
        logging.DEBUG
    )
    logging.getLogger("google_adk.google.adk.plugins.debug_logging_plugin").setLevel(
        logging.DEBUG
    )
    logging.info("ADK debug logging is enabled")
    return [CloudLoggingDebugPlugin()]

# Variables
project_id = gcp_config.PROJECT_ID
region = gcp_config.REGION
model_armor_template_id = f"projects/{project_id}/locations/{region}/templates/{agent_config.MODEL_ARMOR_TEMPLATE_ID}"

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

tools = get_mcp_servers_tools(mcp_servers)
debug_plugins = _build_debug_plugins(agent_config)

root_agent = Agent(
    model=Gemini(
        model_name=agent_config.MODEL_NAME,
        retry_options=agent_retry_options,
    ),
    name=agent_config.AGENT_NAME,
    generate_content_config=agent_settings,
    instruction=agent_config.AGENT_INSTRUCTION,
    tools=tools,
)

app = agent_engines.AdkApp(agent=root_agent, plugins=debug_plugins)
