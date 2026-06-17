from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from typing import Annotated, Self


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
            default="http://localhost:8000/dev-ui/",
            description="Shared OAuth 2.0 Redirect URI for APIs used by the agent.",
        ),
    ]
    AUTH_URI: Annotated[
        str,
        Field(
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
            description=(
                "The URL used by the application to exchange an authorization code for an access token (and refresh token). "
                "This is required for the second step of the OAuth 2.0 Authorization Code flow, "
                "used by the ADK framework to silently fetch the token after the user approves the login."
            ),
        ),
    ]
    TOKEN_ENDPOINT_AUTH_METHOD: Annotated[
        str,
        Field(
            default="client_secret_basic",
            description="The authentication method used when exchanging the code for a token (e.g., client_secret_basic or client_secret_post).",
        ),
    ]


class GoogleAuthConfig(BaseOAuthConfig):
    """Configuration for Google OAuth 2.0 connection parameters."""

    model_config = SettingsConfigDict(
        env_prefix="GOOGLE_OAUTH_",
    )

    AUTH_URI: Annotated[
        str,
        Field(
            default="https://accounts.google.com/o/oauth2/v2/auth",
            description=(
                "The URL where the user is redirected to log in and grant permissions. "
                "This is required for the first step of the OAuth 2.0 Authorization Code flow."
            ),
        ),
    ]
    TOKEN_URI: Annotated[
        str,
        Field(
            default="https://oauth2.googleapis.com/token",
            description=(
                "The URL used by the application to exchange an authorization code for an access token (and refresh token). "
                "This is required for the second step of the OAuth 2.0 Authorization Code flow."
            ),
        ),
    ]


# class MicrosoftAuthConfig(BaseOAuthConfig):
#     """Configuration for Microsoft Entra OAuth 2.0 connection parameters."""
# 
#     model_config = SettingsConfigDict(
#         env_prefix="MICROSOFT_OAUTH_",
#     )
# 
#     TENANT_ID: Annotated[
#         str,
#         Field(
#             default="mock-tenant-id",
#             description="Microsoft Entra Tenant ID.",
#         ),
#     ]
#     AUTH_URI: Annotated[
#         str,
#         Field(
#             default="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
#             description=(
#                 "The URL where the user is redirected to log in and grant permissions. "
#                 "This is required for the first step of the OAuth 2.0 Authorization Code flow."
#             ),
#         ),
#     ]
#     TOKEN_URI: Annotated[
#         str,
#         Field(
#             default="https://login.microsoftonline.com/common/oauth2/v2.0/token",
#             description=(
#                 "The URL used by the application to exchange an authorization code for an access token (and refresh token). "
#                 "This is required for the second step of the OAuth 2.0 Authorization Code flow."
#             ),
#         ),
#     ]
#     # TOKEN_ENDPOINT_AUTH_METHOD: str = "client_secret_post"
# 
#     @model_validator(mode="after")
#     def construct_uris(self) -> Self:
#         """Dynamically injects the TENANT_ID into the OAuth URIs if they still contain 'common'."""
#         if "common" in self.AUTH_URI:
#             self.AUTH_URI = self.AUTH_URI.replace("common", self.TENANT_ID)
#         if "common" in self.TOKEN_URI:
#             self.TOKEN_URI = self.TOKEN_URI.replace("common", self.TENANT_ID)
#         return self


# Global configuration instances
GOOGLE_AUTH_CONFIG = GoogleAuthConfig()
# MICROSOFT_AUTH_CONFIG = MicrosoftAuthConfig()
