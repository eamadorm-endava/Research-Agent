"""Configuration for the custom UI; production defaults fail closed."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UIConfig(BaseSettings):
    """Keep service, identity and upload settings in one validated configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ENVIRONMENT: str = "production"
    PROJECT_ID: str = ""
    PROJECT_NUMBER: str = ""
    REGION: str = "us-central1"
    AGENT_RESOURCE_NAME: str = ""
    AGENT_DISPLAY_NAME: str = "OSIRIS"
    IAP_BACKEND_SERVICES: list[str] = [
        "ui-frontend-elb-prod-backend",
        "ui-frontend-elb-prod-api",
    ]
    IAP_AUDIENCES: list[str] = []
    PUBLIC_BASE_URL: str = "https://osiris.endava.app"
    ALLOWED_ORIGINS: list[str] = ["https://osiris.endava.app"]
    LOCAL_USER_EMAIL: str = ""
    LANDING_ZONE_BUCKET: str = ""
    SERVICE_ACCOUNT_EMAIL: str = ""
    MAX_UPLOAD_BYTES: int = Field(default=20 * 1024 * 1024, gt=0)
    REQUESTS_PER_MINUTE: int = Field(default=30, gt=0)
    OAUTH_STATE_SECONDS: int = Field(default=600, gt=0, le=600)
    HTTP_TIMEOUT_SECONDS: int = Field(default=20, gt=0)
    REQUIRED_PROVIDERS: list[str] = []


UI_CONFIG = UIConfig()
