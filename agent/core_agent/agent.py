from google.adk.tools import load_artifacts

from .builder import AgentBuilder, AppBuilder
from .tools.artifact_tools import GetArtifactURITool
from .tools.ekb_tools import TriggerEKBPipelineTool, CheckIngestionStatusTool
from .tools.time_tools import GetCurrentTimeTool
from .callbacks.before_agent_callbacks import sync_ekb_job_status
from loguru import logger
from .plugins.gemini_enterprise_ingestion import GeminiEnterpriseFileIngestionPlugin
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from .plugins.multimodal_file_injection import MultimodalFileInjectionPlugin
from .plugins.continuation import ContinuationPlugin
from .plugins.metrics.plugin import ResponseTimeMetricsPlugin
from .config import (
    GCP_CONFIG,
    COORDINATOR_CONFIG,
    RESEARCH_AGENT_CONFIG,
    INGESTION_AGENT_CONFIG,
    BigQueryMCPConfig,
    CalendarMCPConfig,
    DriveMCPConfig,
    GCSMCPConfig,
    OneDriveMCPConfig,
    SharePointMCPConfig,
    AtlassianMCPConfig,
    GOOGLE_AUTH_CONFIG,
    MICROSOFT_AUTH_CONFIG,
)

# ---------------------------------------------------------------------------
# MCP Configuration Instantiation
# ---------------------------------------------------------------------------
BIGQUERY_MCP_CONFIG = BigQueryMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
DRIVE_MCP_CONFIG = DriveMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
CALENDAR_MCP_CONFIG = CalendarMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
GCS_MCP_CONFIG = GCSMCPConfig(OAUTH_CONFIG=GOOGLE_AUTH_CONFIG)
ONEDRIVE_MCP_CONFIG = OneDriveMCPConfig(OAUTH_CONFIG=MICROSOFT_AUTH_CONFIG)
SHAREPOINT_MCP_CONFIG = SharePointMCPConfig(OAUTH_CONFIG=MICROSOFT_AUTH_CONFIG)
ATLASSIAN_MCP_CONFIG = AtlassianMCPConfig()


# ---------------------------------------------------------------------------
# 1. Research & Meetings Specialist
# ---------------------------------------------------------------------------
research_agent = (
    AgentBuilder(
        agent_config=RESEARCH_AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
    )
    .with_skills(["meeting-summary", "knowledge-discovery"])
    .with_mcp_servers(
        [
            BIGQUERY_MCP_CONFIG,
            DRIVE_MCP_CONFIG,
            CALENDAR_MCP_CONFIG,
            GCS_MCP_CONFIG,
            ATLASSIAN_MCP_CONFIG,
            ONEDRIVE_MCP_CONFIG,
            SHAREPOINT_MCP_CONFIG,
        ]
    )
    .with_native_tools(
        [
            GetArtifactURITool(),
            GetCurrentTimeTool(),
            load_artifacts,
        ]
    )
    .with_before_agent_callback([sync_ekb_job_status])
    .with_output_key("research_context")
    .build()
)

# ---------------------------------------------------------------------------
# 2. Ingestion Specialist
# ---------------------------------------------------------------------------
ingestion_agent = (
    AgentBuilder(
        agent_config=INGESTION_AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
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
            GetArtifactURITool(),
            TriggerEKBPipelineTool(),
            CheckIngestionStatusTool(),
            load_artifacts,
        ]
    )
    .with_before_agent_callback([sync_ekb_job_status])
    .with_output_key("ekb_ingestion_context")
    .build()
)

# ---------------------------------------------------------------------------
# 3. Coordinator (Root Agent)
# ---------------------------------------------------------------------------
root_agent = (
    AgentBuilder(
        agent_config=COORDINATOR_CONFIG,
        gcp_config=GCP_CONFIG,
    )
    .with_subagents([research_agent, ingestion_agent])
    .with_before_agent_callback([sync_ekb_job_status])
    .with_native_tools([GetArtifactURITool(), load_artifacts])
    .build()
)

app = (
    AppBuilder(
        agent=root_agent,
        gcp_config=GCP_CONFIG,
        agent_config=COORDINATOR_CONFIG,
    )
    .with_plugins(
        (
            # SaveFilesAsArtifactsPlugin targets ADK Web UI only; in production,
            # GeminiEnterpriseFileIngestionPlugin handles upload persistence instead.
            [
                GeminiEnterpriseFileIngestionPlugin(),
                MultimodalFileInjectionPlugin(),
                ContinuationPlugin(),
                ResponseTimeMetricsPlugin(),
            ]
            if GCP_CONFIG.PROD_EXECUTION
            else [
                SaveFilesAsArtifactsPlugin(),
                MultimodalFileInjectionPlugin(),
                ContinuationPlugin(),
                ResponseTimeMetricsPlugin(),
            ]
        )
    )
    .build()
)

logger.info("ADK Multi-Agent application initialized and ready for execution.")
