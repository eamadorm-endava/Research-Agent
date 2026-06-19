from .agent_settings import (
    GCP_CONFIG,
    COORDINATOR_CONFIG,
    RESEARCH_AGENT_CONFIG,
    INGESTION_AGENT_CONFIG,
    GCPConfig,
    BaseAgentConfig,
    CoordinatorConfig,
    ResearchAgentConfig,
    IngestionAgentConfig,
)
from .oauth_settings import (
    GOOGLE_AUTH_CONFIG,
    MICROSOFT_AUTH_CONFIG,
    BaseOAuthConfig,
    GoogleAuthConfig,
    MicrosoftAuthConfig,
)
from .mcp_settings import (
    BaseMCPConfig,
    BigQueryMCPConfig,
    CalendarMCPConfig,
    DriveMCPConfig,
    GCSMCPConfig,
    OneDriveMCPConfig,
    AtlassianMCPConfig,
    SharePointMCPConfig,
)

__all__ = [
    # Singleton config instances (primary external API)
    "GCP_CONFIG",
    "COORDINATOR_CONFIG",
    "RESEARCH_AGENT_CONFIG",
    "INGESTION_AGENT_CONFIG",
    "GOOGLE_AUTH_CONFIG",
    "MICROSOFT_AUTH_CONFIG",
    # Config classes (needed for type hints and MCP instantiation)
    "GCPConfig",
    "BaseAgentConfig",
    "CoordinatorConfig",
    "ResearchAgentConfig",
    "IngestionAgentConfig",
    "BaseOAuthConfig",
    "GoogleAuthConfig",
    "MicrosoftAuthConfig",
    "BaseMCPConfig",
    "BigQueryMCPConfig",
    "CalendarMCPConfig",
    "DriveMCPConfig",
    "GCSMCPConfig",
    "OneDriveMCPConfig",
    "AtlassianMCPConfig",
    "SharePointMCPConfig",
]
