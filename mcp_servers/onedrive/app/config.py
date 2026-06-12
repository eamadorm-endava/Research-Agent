from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MainFolder(StrEnum):
    """Enumeration of the main entry points (folders) available to the user in OneDrive."""

    MY_FILES = "MY_FILES"
    SHARED_WITH_ME = "SHARED_WITH_ME"
    RECENT_FILES = "RECENT_FILES"

    def get_endpoint(self, query: Optional[str] = None) -> str:
        """
        Returns the specific Microsoft Graph API endpoint for performing a global search within this folder space.
        Unlike list_endpoint (which is used for deterministic browsing of root contents), get_endpoint is utilized by
        the find_items tool to inject search queries and perform fuzzy matching across the drive.

        Args:
            query: Optional[str] -> The search string to inject into the endpoint, or None for native fallback.

        Returns:
            str -> The Microsoft Graph API endpoint for searching.
        """
        if self == self.MY_FILES:
            return (
                f"/me/drive/root/search(q='{query}')"
                if query
                else "/me/drive/root/children"
            )
        elif self == self.SHARED_WITH_ME:
            return "/me/insights/shared?$expand=resource"
        elif self == self.RECENT_FILES:
            return "/me/drive/recent"
        return "/me/drive/root/search(q='')"

    @property
    def list_endpoint(self) -> str:
        """
        Returns the specific Microsoft Graph API endpoint for listing the root contents of this folder space.
        Unlike get_endpoint (which is used for fuzzy searching), list_endpoint is utilized by the list_folder_contents
        tool for deterministic, non-recursive structural browsing.

        Args:
            None

        Returns:
            str -> The Microsoft Graph API endpoint for listing children.
        """
        mapping = {
            self.MY_FILES: "/me/drive/root/children",
            self.SHARED_WITH_ME: "/me/drive/sharedWithMe",
            self.RECENT_FILES: "/me/drive/recent",
        }
        return mapping[self]


class OneDriveMCPConfigBase(BaseSettings):
    """Shared immutable configuration base for the OneDrive MCP server."""

    model_config = SettingsConfigDict(
        extra="ignore",
        frozen=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


class OneDriveAuthConfig(OneDriveMCPConfigBase):
    """Configuration for Microsoft Entra authentication settings."""

    TENANT_ID: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("MICROSOFT_TENANT_ID", "TENANT_ID"),
            description="The Microsoft Entra Tenant ID.",
        ),
    ]
    CLIENT_ID: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("MICROSOFT_CLIENT_ID", "CLIENT_ID"),
            description="The Microsoft Entra App Registration Client ID.",
        ),
    ]
    CLIENT_SECRET: Annotated[
        str,
        Field(
            default="",
            validation_alias=AliasChoices("MICROSOFT_CLIENT_SECRET", "CLIENT_SECRET"),
            description="The Microsoft Entra App Registration Client Secret.",
        ),
    ]
    SCOPES: Annotated[
        list[str],
        Field(
            default=[
                "offline_access",
                "Files.Read.All",
                "Sites.Read.All",
            ],
            description="The OAuth scopes required for OneDrive and SharePoint access.",
        ),
    ]


class OneDriveServerConfig(OneDriveMCPConfigBase):
    """Configuration for the MCP server network/runtime settings."""

    graph_api_base_url: Annotated[
        str,
        Field(
            default="https://graph.microsoft.com/v1.0",
            description="The base URL for the Microsoft Graph API.",
        ),
    ]

    server_name: Annotated[
        str,
        Field(
            default="osiris-onedrive-mcp-server",
            description="Published name of the OneDrive MCP server.",
        ),
    ]
    default_host: Annotated[
        str,
        Field(
            default="0.0.0.0",
            description="Default interface the OneDrive MCP server binds to.",
        ),
    ]
    default_port: Annotated[
        int,
        Field(
            default=8083,
            ge=1,
            le=65535,
            description="Default port for the OneDrive MCP server.",
        ),
    ]
    default_log_level: Annotated[
        str,
        Field(
            default="info",
            description="Default log level for the local OneDrive MCP server.",
        ),
    ]
    stateless_http: Annotated[
        bool,
        Field(
            default=True,
            description="Whether the server should use stateless HTTP mode.",
        ),
    ]
    landing_zone_bucket: Annotated[
        str,
        Field(
            default="mock-landing-zone-bucket",
            validation_alias=AliasChoices(
                "GCS_LANDING_ZONE_BUCKET", "LANDING_ZONE_BUCKET"
            ),
            description="The GCS bucket acting as the AI Agent landing zone.",
        ),
    ]
    max_tree_depth: Annotated[
        int,
        Field(
            default=3,
            description="Maximum depth for recursive directory tree building.",
        ),
    ]
    max_files_per_page: Annotated[
        int,
        Field(
            default=20,
            description="Maximum number of objects returned per directory or page.",
        ),
    ]
    cache_ttl_seconds: Annotated[
        int,
        Field(
            default=600,
            description="Time-to-live for cached Graph API responses and read files in seconds.",
        ),
    ]


ONEDRIVE_AUTH_CONFIG = OneDriveAuthConfig()
ONEDRIVE_SERVER_CONFIG = OneDriveServerConfig()
