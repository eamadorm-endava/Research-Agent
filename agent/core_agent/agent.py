from vertexai import agent_engines

from .builder import AgentBuilder
from .config import (
    GCP_CONFIG,
    AGENT_CONFIG,
    BIGQUERY_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    GCS_MCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
)
from .plugins import ArtifactTrackingSaveFilesPlugin
from .tools import transfer_uploaded_artifact_to_landing_zone

mcp_servers_to_mount = [
    BIGQUERY_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    GCS_MCP_CONFIG,
]

skills_to_mount = [
    "meeting-summary",
]

native_tools_to_mount = [
    transfer_uploaded_artifact_to_landing_zone,
]


agent_builder = (
    AgentBuilder(
        agent_config=AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_skills(skills_to_mount)
    .with_mcp_servers(mcp_servers_to_mount)
    .with_tools(native_tools_to_mount)
    .with_artifact_root_dir(GCS_MCP_CONFIG.ARTIFACTS_DIR)
)

root_agent = agent_builder.build()

app = agent_engines.AdkApp(
    agent=root_agent,
    plugins=[ArtifactTrackingSaveFilesPlugin()],
    artifact_service_builder=agent_builder.build_artifact_service,
)
