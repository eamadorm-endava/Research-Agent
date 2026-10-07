from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class UIConfig(BaseSettings):
    """Configuration for the Custom UI Backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    AGENT_RESOURCE_NAME: Annotated[
        str,
        Field(
            default="mock-agent-runtime-endpoint",
            description="The full resource name of the deployed Agent Platform - Reasoning Engine.",
        ),
    ]


# Global configuration instance
UI_CONFIG = UIConfig()
