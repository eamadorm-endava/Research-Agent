from google.adk.tools import load_artifacts

from .builder import AgentBuilder, AppBuilder
from .config import (
    GCP_CONFIG,
    COORDINATOR_CONFIG,
    RESEARCH_AGENT_CONFIG,
    INGESTION_AGENT_CONFIG,
    BIGQUERY_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    GCS_MCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
)

from .tools.artifact_tools import (
    GetArtifactUriTool,
    ImportGcsToArtifactTool,
)
from .tools.kb_tools import TriggerEKBPipelineTool, CheckIngestionStatusTool
from .tools.time_tools import GetCurrentTimeTool
from .callbacks.ingestion_status import sync_ingestion_status
from loguru import logger

# ---------------------------------------------------------------------------
# 1. Research & Meetings Specialist
# ---------------------------------------------------------------------------
research_agent = (
    AgentBuilder(
        agent_config=RESEARCH_AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_skills(["meeting-summary", "knowledge-discovery"])
    .with_mcp_servers(
        [
            BIGQUERY_MCP_CONFIG,
            DRIVE_MCP_CONFIG,
            CALENDAR_MCP_CONFIG,
            GCS_MCP_CONFIG,
        ]
    )
    .with_native_tools(
        [
            GetArtifactUriTool(),
            ImportGcsToArtifactTool(),
            GetCurrentTimeTool(),
            load_artifacts,
        ]
    )
    .with_output_key("research_context")
    .build(enable_artifact_rendering=False)
)

# ---------------------------------------------------------------------------
# 2. Ingestion Specialist
# ---------------------------------------------------------------------------
ingestion_agent = (
    AgentBuilder(
        agent_config=INGESTION_AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_skills(["kb-file-ingestion"])
    .with_mcp_servers(
        [
            BIGQUERY_MCP_CONFIG,
            GCS_MCP_CONFIG,
        ]
    )
    .with_native_tools(
        [
            GetArtifactUriTool(),
            ImportGcsToArtifactTool(),
            TriggerEKBPipelineTool(),
            CheckIngestionStatusTool(),
            load_artifacts,
        ]
    )
    .with_output_key("ekb_ingestion_context")
    .build(enable_artifact_rendering=False)
)

# ---------------------------------------------------------------------------
# 3. Coordinator (Root Agent)
# ---------------------------------------------------------------------------
root_agent = (
    AgentBuilder(
        agent_config=COORDINATOR_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_subagents([research_agent, ingestion_agent])
    .with_before_agent_callback(sync_ingestion_status)
    .with_native_tools([GetArtifactUriTool(), load_artifacts])
    .build()
)

app = AppBuilder(
    agent=root_agent,
    gcp_config=GCP_CONFIG,
    agent_config=COORDINATOR_CONFIG,
).build()

logger.info("ADK Multi-Agent application initialized and ready for execution.")
