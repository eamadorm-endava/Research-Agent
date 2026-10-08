"""Validated inputs and constant provider paths for the UI authentication flow."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .config import PROVIDER_COOKIES


class ConnectionStatus(BaseModel):
    """Report only which connections the authenticated user still needs."""

    missing_providers: Annotated[
        list[Literal["google", "microsoft", "atlassian"]],
        Field(description="Providers requiring consent, in connection order."),
    ]


class OAuthProviderRequest(BaseModel):
    """Validate the supported provider before selecting server-owned metadata."""

    provider: Annotated[
        Literal["google", "microsoft", "atlassian"],
        Field(description="Supported OAuth provider."),
    ]

    @property
    def cookie_settings(self) -> dict[str, str]:
        """Return fixed cookie metadata, independent of URL string construction."""
        return PROVIDER_COOKIES[self.provider].copy()

    @property
    def callback_path(self) -> str:
        """Construct the callback path from the provider's fixed route prefix."""
        return f"{self.cookie_settings['path']}/callback"
