from pathlib import Path
from typing import Annotated, Optional
from pydantic import Field, SecretStr, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger

_ATLASSIAN_DIR = Path(__file__).parent.parent
_ENV_FILE = _ATLASSIAN_DIR / ".env"


class AtlassianCredentials(BaseModel):
    """Structured credentials for Atlassian authentication."""

    jira_user_email: str = Field(alias="JIRA_USER_EMAIL")
    jira_api_token: SecretStr = Field(alias="JIRA_API_TOKEN")
    jira_instance_url: str = Field(alias="JIRA_INSTANCE_URL")
    jira_cloud_id: Optional[str] = Field(default="", alias="JIRA_CLOUD_ID")



class AtlassianMcpConfigBase(BaseSettings):
    """Shared immutable configuration base for the Atlassian MCP server."""

    model_config = SettingsConfigDict(
        env_file=(str(_ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )


class AtlassianAPIConfig(AtlassianMcpConfigBase):
    """Configuration for Atlassian API credentials and scopes."""

    atlassian_credentials_json: Annotated[
        Optional[str],
        Field(
            default=None,
            description="JSON string containing user email, API token, instance URL, and cloud ID.",
            validation_alias="ATLASSIAN_CREDENTIALS",
        ),
    ]

    jira_user_email: Annotated[
        Optional[str],
        Field(
            default=None,
            description="User email for Jira API.",
            validation_alias="JIRA_USER_EMAIL",
        ),
    ]

    jira_api_token: Annotated[
        Optional[SecretStr],
        Field(
            default=None,
            description="API token for Jira API.",
            validation_alias="JIRA_API_TOKEN",
        ),
    ]

    jira_instance_url: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Instance URL for Jira API.",
            validation_alias="JIRA_INSTANCE_URL",
        ),
    ]

    jira_cloud_id: Annotated[
        Optional[str],
        Field(
            default="",
            description="Cloud ID for Jira API.",
            validation_alias="JIRA_CLOUD_ID",
        ),
    ]

    @property
    def credentials(self) -> AtlassianCredentials:
        """Parses and returns the structured Atlassian credentials."""
        # 1. Try individual environment variables first
        if self.jira_user_email and self.jira_api_token and self.jira_instance_url:
            return AtlassianCredentials(
                JIRA_USER_EMAIL=self.jira_user_email,
                JIRA_API_TOKEN=self.jira_api_token,
                JIRA_INSTANCE_URL=self.jira_instance_url,
                JIRA_CLOUD_ID=self.jira_cloud_id or "",
            )

        # 2. Try parsing from JSON secret next
        if self.atlassian_credentials_json:
            try:
                raw_json = self.atlassian_credentials_json.strip()
                if raw_json and raw_json != "{}":
                    # Strip wrapping quotes if any (common when loaded from shell variables)
                    if raw_json.startswith("'") and raw_json.endswith("'"):
                        raw_json = raw_json[1:-1]
                    return AtlassianCredentials.model_validate_json(raw_json)
            except Exception as e:
                logger.warning(f"Failed to parse ATLASSIAN_CREDENTIALS JSON: {e}.")

        raise ValueError(
            "Missing Atlassian credentials. Provide either JIRA_USER_EMAIL, JIRA_API_TOKEN, and JIRA_INSTANCE_URL or ATLASSIAN_CREDENTIALS JSON."
        )


class AtlassianServerConfig(AtlassianMcpConfigBase):
    """Configuration for the MCP server network and runtime settings."""

    server_name: Annotated[
        str,
        Field(
            default="atlassian-mcp-server",
            description="Name of the Atlassian MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Interface to bind to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8085,
            ge=1,
            le=65535,
            description="Default port.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="INFO",
            description="Default log level.",
        ),
    ]
    stateless_http: Annotated[
        bool,
        Field(
            default=True,
            description="Run in stateless HTTP mode.",
        ),
    ]
    landing_zone_bucket: Annotated[
        str,
        Field(
            default="",
            description="Landing Zone bucket name for file uploads.",
            validation_alias="LANDING_ZONE_BUCKET",
        ),
    ]


ATLASSIAN_API_CONFIG = AtlassianAPIConfig()
ATLASSIAN_SERVER_CONFIG = AtlassianServerConfig()
