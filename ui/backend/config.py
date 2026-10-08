from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UIConfig(BaseSettings):
    """Configuration for the Custom UI Backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "production"
    LOCAL_USER_EMAIL: str = ""
    PROJECT_NUMBER: str = ""
    PUBLIC_BASE_URL: str = "https://osiris.endava.app"
    IAP_BACKEND_SERVICES: list[str] = [
        "ui-frontend-elb-prod-backend",
        "ui-frontend-elb-prod-api",
    ]
    IAP_AUDIENCES: list[str] = []
    OAUTH_STATE_SECONDS: int = 600
    HTTP_TIMEOUT_SECONDS: int = 20

    AGENT_RESOURCE_NAME: Annotated[
        str,
        Field(
            default="mock-agent-runtime-endpoint",
            description="The full resource name of the deployed Agent Platform - Reasoning Engine.",
        ),
    ]


# Global configuration instance
UI_CONFIG = UIConfig()
