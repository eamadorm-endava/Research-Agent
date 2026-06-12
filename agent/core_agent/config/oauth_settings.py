from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class BaseOAuthConfig(BaseSettings):
    """Holds shared OAuth 2.0 credentials used across all MCP server connections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )

    CLIENT_ID: Annotated[
        str,
        Field(
            default="mock-oauth-client-id",
            description="Shared OAuth 2.0 Client ID for APIs used by the agent.",
        ),
    ]
    CLIENT_SECRET: Annotated[
        str,
        Field(
            default="mock-oauth-client-secret",
            description="Shared OAuth 2.0 Client Secret for APIs used by the agent.",
        ),
    ]
    REDIRECT_URI: Annotated[
        str,
        Field(
            default="http://localhost:8000/dev-ui",
            description="Shared OAuth 2.0 Redirect URI for APIs used by the agent.",
        ),
    ]
    AUTH_URI: Annotated[
        str,
        Field(
            default="https://accounts.google.com/o/oauth2/v2/auth",
            description=(
                "The URL where the user is redirected to log in and grant permissions. "
                "This is required for the first step of the OAuth 2.0 Authorization Code flow, "
                "used specifically during local development when the ADK frontend redirects the developer to authenticate."
            ),
        ),
    ]
    TOKEN_URI: Annotated[
        str,
        Field(
            default="https://oauth2.googleapis.com/token",
            description=(
                "The URL used by the application to exchange an authorization code for an access token (and refresh token). "
                "This is required for the second step of the OAuth 2.0 Authorization Code flow, "
                "used by the ADK framework to silently fetch the token after the user approves the login."
            ),
        ),
    ]


class GoogleAuthConfig(BaseOAuthConfig):
    model_config = SettingsConfigDict(
        env_prefix="GOOGLE_OAUTH_",
    )


class MicrosoftAuthConfig(BaseOAuthConfig):
    model_config = SettingsConfigDict(
        env_prefix="MICROSOFT_OAUTH_",
    )


# Global configuration instances
GOOGLE_AUTH_CONFIG = GoogleAuthConfig()
MICROSOFT_AUTH_CONFIG = MicrosoftAuthConfig()
