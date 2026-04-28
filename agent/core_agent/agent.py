from .builder import AgentBuilder
from .app_factory import create_adk_app
from .config import (
    GCP_CONFIG,
    AGENT_CONFIG,
    BIGQUERY_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    GCS_MCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
)

from google.adk.apps.app import App
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.adk.tools import load_artifacts
from .internal_tools.artifact_tools import GetArtifactUriTool

mcp_servers_to_mount = [
    BIGQUERY_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    GCS_MCP_CONFIG,
]

skills_to_mount = [
    "meeting-summary",
]

root_agent = (
    AgentBuilder(
        agent_config=AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_skills(skills_to_mount)
    .with_mcp_servers(mcp_servers_to_mount)
    .with_internal_tools([GetArtifactUriTool(), load_artifacts])
    .build()
)

# Select the application type based on the environment
if GCP_CONFIG.PROD_EXECUTION:
    # AdkApp (Vertex AI template) used for production deployment to Agent Engine
    app = create_adk_app(
        agent=root_agent,
        artifact_bucket=GCP_CONFIG.ARTIFACT_BUCKET,
        app_name=AGENT_CONFIG.AGENT_NAME,
        enable_tracing=AGENT_CONFIG.ENABLE_TRACING,
    )
else:
    # Standard ADK App object used by the 'adk web' CLI for local development
    app = App(
        name=AGENT_CONFIG.AGENT_NAME,
        root_agent=root_agent,
        plugins=[SaveFilesAsArtifactsPlugin()],
    )
