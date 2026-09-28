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
            default="projects/753988132239/locations/us-central1/reasoningEngines/915311544286314496",
            description="The full resource name of the deployed Vertex AI Reasoning Engine.",
        ),
    ]


# Global configuration instance
UI_CONFIG = UIConfig()
