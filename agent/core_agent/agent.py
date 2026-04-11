from .builder import AgentBuilder
from .config import (
    AGENT_CONFIG,
    BIGQUERY_MCP_CONFIG,
    CALENDAR_MCP_CONFIG,
    DRIVE_MCP_CONFIG,
    GCP_CONFIG,
    GCS_MCP_CONFIG,
    GOOGLE_AUTH_CONFIG,
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

app = (
    AgentBuilder(
        agent_config=AGENT_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_skills(skills_to_mount)
    .with_mcp_servers(mcp_servers_to_mount)
    .build()
)
