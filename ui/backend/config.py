from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

OAUTH_CALLBACK_SCRIPT = (
    "window.onload = function() { setTimeout(function() { window.close(); }, 2000); };"
)


# CSP fingerprint of the fixed public script above; verified by the regression test.
OAUTH_CALLBACK_CSP_SOURCE = "'sha256-f/Ri5mz3Ga19XOXQ5kKofBviUCTr6dgE9st/E1+v7gg='"


PROVIDER_COOKIES = {
    "google": {"name": "oauth_google", "path": "/api/auth/google"},
    "microsoft": {"name": "oauth_microsoft", "path": "/api/auth/microsoft"},
    "atlassian": {"name": "oauth_atlassian", "path": "/api/auth/atlassian"},
}


class UIConfig(BaseSettings):
    """Configuration for the Custom UI Backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Annotated[
        str, Field(default="production", description="Runtime environment.")
    ]
    LOCAL_USER_EMAIL: Annotated[
        str, Field(default="", description="Explicit development identity.")
    ]
    PROJECT_NUMBER: Annotated[
        str, Field(default="", description="GCP project number for IAP audiences.")
    ]
    PUBLIC_BASE_URL: Annotated[
        str,
        Field(default="https://osiris.endava.app", description="Public OAuth origin."),
    ]
    IAP_BACKEND_SERVICES: Annotated[
        list[str],
        Field(
            default_factory=lambda: [
                "ui-frontend-elb-prod-backend",
                "ui-frontend-elb-prod-api",
            ],
            description="Trusted IAP backend names.",
        ),
    ]
    IAP_AUDIENCES: Annotated[
        list[str],
        Field(default_factory=list, description="Explicit trusted audience overrides."),
    ]
    OAUTH_STATE_SECONDS: Annotated[
        int, Field(default=600, gt=0, le=600, description="OAuth transaction lifetime.")
    ]
    HTTP_TIMEOUT_SECONDS: Annotated[
        int, Field(default=20, gt=0, le=60, description="Provider HTTP timeout.")
    ]
    REQUESTS_PER_MINUTE: Annotated[
        int,
        Field(
            default=120,
            gt=0,
            description="Per-instance request limit per remote address.",
        ),
    ]

    @property
    def allowed_origins(self) -> list[str]:
        """Allow browser requests only from the configured public origin."""
        return [self.PUBLIC_BASE_URL.rstrip("/")]

    AGENT_RESOURCE_NAME: Annotated[
        str,
        Field(
            default="mock-agent-runtime-endpoint",
            description="The full resource name of the deployed Agent Platform - Reasoning Engine.",
        ),
    ]


# Global configuration instance
UI_CONFIG = UIConfig()
