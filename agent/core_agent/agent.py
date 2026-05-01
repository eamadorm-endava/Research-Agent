from .builder import AgentBuilder, AppBuilder
from .config import (
    GCP_CONFIG,
    AGENT_CONFIG,
    BIGQUERY_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    GCS_MCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
)

from google.adk.tools import load_artifacts
from .tools.artifact_tools import (
    GetArtifactUriTool,
    ImportGcsToArtifactTool,
)

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
    .with_native_tools(
        [
            GetArtifactUriTool(),
            ImportGcsToArtifactTool(),
            load_artifacts,
        ]
    )
    .build()
)

app = AppBuilder(
    agent=root_agent,
    gcp_config=GCP_CONFIG,
    agent_config=AGENT_CONFIG,
).build()
