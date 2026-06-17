import os
from pathlib import Path

# Automatically load environment variables from .env files into os.environ
for env_path in [
    Path.cwd() / ".env",
    Path.cwd() / "agent" / ".env",
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent / ".env",
]:
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    # Set the environment variable
                    os.environ[key] = val
        except Exception:
            pass

from .agent_settings import (
    GCP_CONFIG,
    COORDINATOR_CONFIG,
    RESEARCH_AGENT_CONFIG,
    INGESTION_AGENT_CONFIG,
    BaseAgentConfig,
    CoordinatorConfig,
    ResearchAgentConfig,
    IngestionAgentConfig,
    GCPConfig,
)
from .oauth_settings import (
    BaseOAuthConfig,
    GoogleAuthConfig,
    # MicrosoftAuthConfig,
    GOOGLE_AUTH_CONFIG,
    # MICROSOFT_AUTH_CONFIG,
)
from .mcp_settings import (
    BaseMCPConfig,
    BigQueryMCPConfig,
    CalendarMCPConfig,
    DriveMCPConfig,
    GCSMCPConfig,
    # OneDriveMCPConfig,
    AtlassianMCPConfig,
)

__all__ = [
    "BaseAgentConfig",
    "CoordinatorConfig",
    "ResearchAgentConfig",
    "IngestionAgentConfig",
    "GCPConfig",
    "BaseOAuthConfig",
    "GoogleAuthConfig",
    # "MicrosoftAuthConfig",
    "BaseMCPConfig",
    "BigQueryMCPConfig",
    "CalendarMCPConfig",
    "DriveMCPConfig",
    "GCSMCPConfig",
    # "OneDriveMCPConfig",
    "AtlassianMCPConfig",
    "GCP_CONFIG",
    "COORDINATOR_CONFIG",
    "RESEARCH_AGENT_CONFIG",
    "INGESTION_AGENT_CONFIG",
    "GOOGLE_AUTH_CONFIG",
    # "MICROSOFT_AUTH_CONFIG",
]
