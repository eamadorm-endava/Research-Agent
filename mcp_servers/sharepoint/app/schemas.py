from enum import StrEnum
from typing import Annotated, Any, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthenticationError(Exception):
    """Raised when delegated Microsoft Graph authentication fails."""


class SharePointSchemaModel(BaseModel):
    """Shared schema base for the SharePoint MCP server."""

    model_config = ConfigDict(extra="forbid")


class SharePointItemKind(StrEnum):
    """Supported SharePoint drive item categories."""

    FILE = "file"
    FOLDER = "folder"
    PACKAGE = "package"
    UNKNOWN = "unknown"


class AgentDependencies(SharePointSchemaModel):
    """Context injected by the agent framework and hidden from the LLM schema."""

    app_name: Annotated[
        str,
        Field(description="The name of the calling application or agent."),
    ]
    user_id: Annotated[
        str,
        Field(description="The unique identifier of the user using the agent."),
    ]
    session_id: Annotated[
        str,
        Field(description="The current session or conversation ID with the agent."),
    ]


class BaseRequest(SharePointSchemaModel):
    """Base request carrying hidden agent dependencies when they are required."""

    dependencies: Annotated[
        Optional[AgentDependencies],
        Field(
            default=None,
            exclude=True,
            description=(
                "Parameters injected by the framework. These are hidden from the LLM "
                "to prevent hallucinated user, application, or session values."
            ),
        ),
    ]

    @property
    def required_dependencies(self) -> AgentDependencies:
        """Returns injected dependencies or raises a deterministic validation error.

        Args:
            None -> This property only reads validated request state.

        Returns:
            AgentDependencies -> Injected application, user, and session context.
        """
        if self.dependencies is None:
            raise ValueError("Missing injected agent dependencies.")
        return self.dependencies


class BaseResponse(SharePointSchemaModel):
    """Common response fields returned by every SharePoint MCP tool."""

    execution_status: Annotated[
        Literal["success", "error"],
        Field(description="Whether the tool completed successfully."),
    ]
    execution_message: Annotated[
        str,
        Field(
            default="Execution completed successfully.",
            description="Human-readable execution details or error summary.",
        ),
    ]


MAX_RESULTS = Annotated[
    int,
    Field(
        default=25,
        ge=1,
        le=200,
        description="Maximum number of SharePoint items to return.",
    ),
]
MAX_TEXT_CHARS = Annotated[
    int,
    Field(
        default=12000,
        ge=500,
        le=50000,
        description="Maximum number of extracted text characters to return.",
    ),
]
SITE_ID = Annotated[
    str,
    Field(min_length=1, description="Microsoft Graph SharePoint site identifier."),
]
DRIVE_ID = Annotated[
    str,
    Field(min_length=1, description="Microsoft Graph drive identifier."),
]
DRIVE_ITEM_ID = Annotated[
    str,
    Field(min_length=1, description="Microsoft Graph driveItem identifier."),
]
OPTIONAL_DRIVE_ITEM_ID = Annotated[
    Optional[str],
    Field(default=None, min_length=1, description="Optional driveItem identifier."),
]
LIST_ID = Annotated[
    str,
    Field(min_length=1, description="Microsoft Graph SharePoint list identifier."),
]
PAGE_ID = Annotated[
    str,
    Field(min_length=1, description="Microsoft Graph SharePoint site page identifier."),
]
FOLDER_PATH = Annotated[
    Optional[str],
    Field(
        default=None,
        min_length=1,
        max_length=1024,
        pattern=r"^[^\\:*?\"<>|]+(?:/[^\\:*?\"<>|]+)*/?$",
        description="Optional root-relative folder path, for example Shared Documents/Reports.",
    ),
]
SEARCH_QUERY = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        description="Search text used to find SharePoint sites or drive items.",
    ),
]
OPTIONAL_FILENAME = Annotated[
    Optional[str],
    Field(
        default=None,
        min_length=1,
        max_length=255,
        pattern=r"^[^\\/:*?\"<>|]+$",
        description="Optional filename override for the landing-zone copy.",
    ),
]


class SharePointSite(SharePointSchemaModel):
    """Compact SharePoint site metadata returned to the agent."""

    site_id: Annotated[str, Field(description="Microsoft Graph site ID.")]
    name: Annotated[Optional[str], Field(default=None, description="Site URL name.")]
    display_name: Annotated[
        Optional[str], Field(default=None, description="Human-readable site title.")
    ]
    web_url: Annotated[
        Optional[str], Field(default=None, description="Browser URL for the site.")
    ]
    created_at: Annotated[
        Optional[str], Field(default=None, description="Site creation timestamp.")
    ]
    last_modified_at: Annotated[
        Optional[str], Field(default=None, description="Last modified timestamp.")
    ]


class SharePointSiteDetail(SharePointSite):
    """Expanded SharePoint site metadata for site-level reasoning."""

    description: Annotated[
        Optional[str],
        Field(default=None, description="Site description, when available."),
    ]
    hostname: Annotated[
        Optional[str], Field(default=None, description="SharePoint tenant hostname.")
    ]
    sharepoint_ids: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="Raw Graph sharepointIds metadata useful for traceability.",
        ),
    ]


class SharePointDrive(SharePointSchemaModel):
    """Compact SharePoint document library drive metadata."""

    drive_id: Annotated[str, Field(description="Microsoft Graph drive ID.")]
    name: Annotated[str, Field(description="Document library display name.")]
    drive_type: Annotated[
        Optional[str],
        Field(default=None, description="Graph drive type, when available."),
    ]
    web_url: Annotated[
        Optional[str],
        Field(default=None, description="Browser URL for the document library."),
    ]
    created_at: Annotated[
        Optional[str], Field(default=None, description="Drive creation timestamp.")
    ]
    last_modified_at: Annotated[
        Optional[str],
        Field(default=None, description="Drive last modified timestamp."),
    ]


class SharePointListResource(SharePointSchemaModel):
    """Compact metadata for a SharePoint list inside a site."""

    list_id: Annotated[str, Field(description="Microsoft Graph list ID.")]
    name: Annotated[
        Optional[str], Field(default=None, description="Internal list name.")
    ]
    display_name: Annotated[
        Optional[str], Field(default=None, description="Human-readable list title.")
    ]
    web_url: Annotated[
        Optional[str], Field(default=None, description="Browser URL for the list.")
    ]
    list_template: Annotated[
        Optional[str], Field(default=None, description="SharePoint list template name.")
    ]
    created_at: Annotated[
        Optional[str], Field(default=None, description="List creation timestamp.")
    ]
    last_modified_at: Annotated[
        Optional[str], Field(default=None, description="List last modified timestamp.")
    ]


class SharePointListItem(SharePointSchemaModel):
    """SharePoint list item fields that can be used directly for answers."""

    item_id: Annotated[str, Field(description="Microsoft Graph listItem ID.")]
    web_url: Annotated[
        Optional[str], Field(default=None, description="Browser URL for the list item.")
    ]
    created_at: Annotated[
        Optional[str], Field(default=None, description="List item creation timestamp.")
    ]
    last_modified_at: Annotated[
        Optional[str],
        Field(default=None, description="List item last modified timestamp."),
    ]
    fields: Annotated[
        dict[str, Any],
        Field(default_factory=dict, description="Visible SharePoint list item fields."),
    ]
    text_preview: Annotated[
        str,
        Field(
            default="", description="Concise text preview assembled from field values."
        ),
    ]


class SharePointPageSummary(SharePointSchemaModel):
    """SharePoint site page metadata returned during site discovery."""

    page_id: Annotated[str, Field(description="Microsoft Graph sitePage ID.")]
    name: Annotated[Optional[str], Field(default=None, description="Page file name.")]
    title: Annotated[Optional[str], Field(default=None, description="Page title.")]
    web_url: Annotated[
        Optional[str], Field(default=None, description="Browser URL for the page.")
    ]
    page_layout: Annotated[
        Optional[str], Field(default=None, description="Graph page layout value.")
    ]
    promotion_kind: Annotated[
        Optional[str],
        Field(default=None, description="Graph page promotion kind value."),
    ]
    created_at: Annotated[
        Optional[str], Field(default=None, description="Page creation timestamp.")
    ]
    last_modified_at: Annotated[
        Optional[str], Field(default=None, description="Page last modified timestamp.")
    ]


class SharePointPageContent(SharePointPageSummary):
    """Readable text extracted from a SharePoint site page payload."""

    content_text: Annotated[
        str,
        Field(
            default="",
            description="Best-effort readable page text extracted from the Graph page payload.",
        ),
    ]
    content_truncated: Annotated[
        bool,
        Field(
            default=False, description="Whether content_text was truncated by limit."
        ),
    ]
    component_count: Annotated[
        int,
        Field(
            default=0, ge=0, description="Approximate number of text fragments found."
        ),
    ]


class SharePointDriveItem(SharePointSchemaModel):
    """Compact SharePoint file or folder metadata returned to the agent."""

    item_id: Annotated[str, Field(description="Microsoft Graph driveItem ID.")]
    name: Annotated[str, Field(description="File or folder display name.")]
    kind: Annotated[
        SharePointItemKind,
        Field(
            description="Whether the driveItem is a file, folder, package, or unknown."
        ),
    ]
    web_url: Annotated[
        Optional[str], Field(default=None, description="Browser URL for the driveItem.")
    ]
    mime_type: Annotated[
        Optional[str],
        Field(default=None, description="File MIME type, when available."),
    ]
    size_bytes: Annotated[
        int,
        Field(default=0, ge=0, description="File or folder size in bytes."),
    ]
    child_count: Annotated[
        Optional[int], Field(default=None, ge=0, description="Folder child count.")
    ]
    created_at: Annotated[
        Optional[str], Field(default=None, description="Creation timestamp.")
    ]
    last_modified_at: Annotated[
        Optional[str], Field(default=None, description="Last modified timestamp.")
    ]
    parent_drive_id: Annotated[
        Optional[str],
        Field(default=None, description="Parent drive ID, when available."),
    ]
    parent_item_id: Annotated[
        Optional[str],
        Field(default=None, description="Parent item ID, when available."),
    ]
    parent_path: Annotated[
        Optional[str], Field(default=None, description="Parent path, when available.")
    ]


class SharePointFileMetadata(SharePointDriveItem):
    """Metadata for a SharePoint file copied into the landing zone."""


class SharePointSiteContentOverview(SharePointSchemaModel):
    """One-call overview of useful content containers inside a SharePoint site."""

    site: Annotated[
        Optional[SharePointSiteDetail],
        Field(default=None, description="Expanded site metadata."),
    ]
    drives: Annotated[
        list[SharePointDrive],
        Field(default_factory=list, description="Document libraries in the site."),
    ]
    lists: Annotated[
        list[SharePointListResource],
        Field(default_factory=list, description="SharePoint lists in the site."),
    ]
    pages: Annotated[
        list[SharePointPageSummary],
        Field(default_factory=list, description="SharePoint pages in the site."),
    ]


class SearchSitesRequest(BaseRequest):
    """Request for searching SharePoint sites available to the signed-in user."""

    query: SEARCH_QUERY
    max_results: MAX_RESULTS


class SearchSitesResponse(BaseResponse):
    """Response containing matching SharePoint sites."""

    query: SEARCH_QUERY
    sites: Annotated[
        list[SharePointSite], Field(default_factory=list, description="Matched sites.")
    ]


class GetSiteRequest(BaseRequest):
    """Request for reading expanded metadata for one SharePoint site."""

    site_id: SITE_ID


class GetSiteResponse(BaseResponse):
    """Response containing one expanded SharePoint site metadata record."""

    site_id: SITE_ID
    site: Annotated[
        Optional[SharePointSiteDetail],
        Field(default=None, description="Expanded SharePoint site metadata."),
    ]


class DiscoverSiteContentRequest(BaseRequest):
    """Request for listing high-level content containers inside one site."""

    site_id: SITE_ID
    max_results: MAX_RESULTS


class DiscoverSiteContentResponse(BaseResponse):
    """Response containing site metadata, libraries, lists, and pages."""

    site_id: SITE_ID
    overview: Annotated[
        Optional[SharePointSiteContentOverview],
        Field(default=None, description="High-level site content overview."),
    ]


class ListSiteDrivesRequest(BaseRequest):
    """Request for listing document-library drives in a SharePoint site."""

    site_id: SITE_ID
    max_results: MAX_RESULTS


class ListSiteDrivesResponse(BaseResponse):
    """Response containing document-library drives for a site."""

    site_id: SITE_ID
    drives: Annotated[
        list[SharePointDrive],
        Field(default_factory=list, description="Document libraries in the site."),
    ]


class ListSiteListsRequest(BaseRequest):
    """Request for listing SharePoint lists in a site."""

    site_id: SITE_ID
    max_results: MAX_RESULTS


class ListSiteListsResponse(BaseResponse):
    """Response containing SharePoint lists for a site."""

    site_id: SITE_ID
    lists: Annotated[
        list[SharePointListResource],
        Field(default_factory=list, description="SharePoint lists in the site."),
    ]


class ListListItemsRequest(BaseRequest):
    """Request for listing readable items from one SharePoint list."""

    site_id: SITE_ID
    list_id: LIST_ID
    max_results: MAX_RESULTS


class ListListItemsResponse(BaseResponse):
    """Response containing SharePoint list item fields."""

    site_id: SITE_ID
    list_id: LIST_ID
    items: Annotated[
        list[SharePointListItem],
        Field(default_factory=list, description="Readable list item fields."),
    ]


class ListSitePagesRequest(BaseRequest):
    """Request for listing SharePoint pages in a site."""

    site_id: SITE_ID
    max_results: MAX_RESULTS


class ListSitePagesResponse(BaseResponse):
    """Response containing SharePoint site page summaries."""

    site_id: SITE_ID
    pages: Annotated[
        list[SharePointPageSummary],
        Field(default_factory=list, description="SharePoint pages in the site."),
    ]


class GetSitePageRequest(BaseRequest):
    """Request for reading text from one SharePoint site page."""

    site_id: SITE_ID
    page_id: PAGE_ID
    max_text_chars: MAX_TEXT_CHARS


class GetSitePageResponse(BaseResponse):
    """Response containing readable SharePoint site page content."""

    site_id: SITE_ID
    page_id: PAGE_ID
    page: Annotated[
        Optional[SharePointPageContent],
        Field(default=None, description="Readable site page content."),
    ]


class ListDriveItemsRequest(BaseRequest):
    """Request for listing children from a SharePoint document library folder."""

    drive_id: DRIVE_ID
    item_id: OPTIONAL_DRIVE_ITEM_ID
    folder_path: FOLDER_PATH
    max_results: MAX_RESULTS

    @model_validator(mode="after")
    def validate_single_folder_selector(self) -> Self:
        """Ensures only one folder addressing mode is provided.

        Args:
            None -> The validator operates on the model instance.

        Returns:
            Self -> The validated request instance.
        """
        if self.item_id and self.folder_path:
            raise ValueError("Use either item_id or folder_path, not both.")
        return self

    @property
    def normalized_folder_path(self) -> Optional[str]:
        """Returns a root-relative folder path without surrounding slashes."""
        if self.folder_path is None:
            return None
        return self.folder_path.strip("/")


class ListDriveItemsResponse(BaseResponse):
    """Response containing SharePoint file and folder metadata."""

    drive_id: DRIVE_ID
    item_id: OPTIONAL_DRIVE_ITEM_ID
    folder_path: FOLDER_PATH
    items: Annotated[
        list[SharePointDriveItem],
        Field(default_factory=list, description="Children in the selected folder."),
    ]


class GetDriveItemRequest(BaseRequest):
    """Request for reading metadata for one SharePoint drive item."""

    drive_id: DRIVE_ID
    item_id: DRIVE_ITEM_ID


class GetDriveItemResponse(BaseResponse):
    """Response containing one SharePoint drive item metadata record."""

    drive_id: DRIVE_ID
    item_id: DRIVE_ITEM_ID
    item: Annotated[
        Optional[SharePointDriveItem],
        Field(default=None, description="Drive item metadata, when found."),
    ]


class SearchDriveItemsRequest(BaseRequest):
    """Request for searching files and folders in a SharePoint drive."""

    drive_id: DRIVE_ID
    query: SEARCH_QUERY
    max_results: MAX_RESULTS


class SearchDriveItemsResponse(BaseResponse):
    """Response containing matching SharePoint drive items."""

    drive_id: DRIVE_ID
    query: SEARCH_QUERY
    items: Annotated[
        list[SharePointDriveItem],
        Field(default_factory=list, description="Matching drive items."),
    ]


class IngestDriveItemRequest(BaseRequest):
    """Request for copying one SharePoint file to the internal landing zone."""

    drive_id: DRIVE_ID
    item_id: DRIVE_ITEM_ID
    filename: OPTIONAL_FILENAME


class IngestDriveItemResponse(BaseResponse):
    """Response used by the multimodal file injection plugin after file copy."""

    drive_id: DRIVE_ID
    item_id: DRIVE_ITEM_ID
    file: Annotated[
        Optional[SharePointFileMetadata],
        Field(default=None, description="Source SharePoint file metadata."),
    ]
    gcs_uri: Annotated[
        Optional[str],
        Field(default=None, description="Canonical GCS URI of the copied file."),
    ]
    mime_type: Annotated[
        str,
        Field(default="application/octet-stream", description="Copied file MIME type."),
    ]
    inject_file_data: Annotated[
        bool,
        Field(
            default=False,
            description="Internal flag that asks the agent plugin to inject file data.",
        ),
    ]
