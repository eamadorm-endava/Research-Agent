from __future__ import annotations

import re
from typing import Annotated, Literal, Optional, Self
from urllib.parse import quote

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from .config import SHAREPOINT_SERVER_CONFIG


JsonObject = dict[str, object]
PageNumber = Annotated[
    int,
    Field(
        description="The page number for paginated results, using 1 as the first page.",
        ge=1,
        default=1,
    ),
]
UseCache = Annotated[
    bool,
    Field(
        description=(
            "Set to False to force a fresh Microsoft Graph call instead of using "
            "the short-lived server cache."
        ),
        default=True,
    ),
]
GraphId = Annotated[
    str,
    Field(
        description="A Microsoft Graph identifier.",
        min_length=1,
    ),
]
OptionalDateTime = Annotated[
    Optional[str],
    Field(
        description="A Microsoft Graph timestamp in ISO 8601 format, when provided.",
        default=None,
    ),
]
OptionalUrl = Annotated[
    Optional[str],
    Field(
        description="A browser URL for the SharePoint resource, when provided.",
        default=None,
    ),
]


class SessionContext(BaseModel):
    """Dependencies injected by the framework for the current session context."""

    app_name: Annotated[
        str,
        Field(
            description="The name of the calling application or agent.", min_length=1
        ),
    ]
    user_id: Annotated[
        str,
        Field(
            description="The unique identifier of the user using the agent.",
            min_length=1,
        ),
    ]
    session_id: Annotated[
        str,
        Field(description="The current session or conversation ID.", min_length=1),
    ]


class BaseRequest(BaseModel):
    """Base request model containing hidden framework-injected dependencies."""

    dependencies: Annotated[
        Optional[SessionContext],
        Field(
            default=None,
            exclude=True,
            description="Framework-injected context hidden from the LLM to prevent hallucination.",
        ),
    ]


class BaseResponse(BaseModel):
    """Base response model containing standard execution status fields."""

    execution_status: Annotated[
        Literal["success", "error"],
        Field(description="The status of the tool execution.", default="success"),
    ]
    execution_message: Annotated[
        str,
        Field(
            description="A descriptive message about the execution result.",
            default="Tool executed successfully.",
        ),
    ]


class PaginatedResponse(BaseResponse):
    """Base response model for tools that return a paginated collection."""

    total_items: Annotated[
        int,
        Field(description="Total number of matching items before page slicing.", ge=0),
    ]
    total_pages: Annotated[
        int,
        Field(description="Total number of result pages available.", ge=1),
    ]
    current_page: Annotated[
        int,
        Field(description="The page number returned in this response.", ge=1),
    ]
    items_in_page: Annotated[
        int,
        Field(description="Number of items returned in this page.", ge=0),
    ]


class SiteMetadata(BaseModel):
    """Normalized metadata describing a SharePoint site."""

    site_id: GraphId
    name: Annotated[Optional[str], Field(description="The site name.", default=None)]
    display_name: Annotated[
        Optional[str],
        Field(description="The human-readable site display name.", default=None),
    ]
    description: Annotated[
        Optional[str],
        Field(description="The site description, when provided.", default=None),
    ]
    web_url: OptionalUrl
    hostname: Annotated[
        Optional[str], Field(description="The SharePoint hostname.", default=None)
    ]
    created_date_time: OptionalDateTime
    last_modified_date_time: OptionalDateTime
    sharepoint_ids: Annotated[
        Optional[JsonObject],
        Field(
            description="Native SharePoint ID metadata returned by Graph.", default=None
        ),
    ]


class DriveMetadata(BaseModel):
    """Normalized metadata describing a SharePoint document-library drive."""

    drive_id: GraphId
    name: Annotated[Optional[str], Field(description="The drive name.", default=None)]
    description: Annotated[
        Optional[str],
        Field(description="The drive description, when provided.", default=None),
    ]
    drive_type: Annotated[
        Optional[str],
        Field(description="The Microsoft Graph drive type.", default=None),
    ]
    web_url: OptionalUrl
    created_date_time: OptionalDateTime
    last_modified_date_time: OptionalDateTime


class SharePointListMetadata(BaseModel):
    """Normalized metadata describing a SharePoint list."""

    list_id: GraphId
    name: Annotated[
        Optional[str], Field(description="The internal list name.", default=None)
    ]
    display_name: Annotated[
        Optional[str],
        Field(description="The user-facing list display name.", default=None),
    ]
    template: Annotated[
        Optional[str], Field(description="The list template type.", default=None)
    ]
    web_url: OptionalUrl
    created_date_time: OptionalDateTime
    last_modified_date_time: OptionalDateTime


class ListItemPreview(BaseModel):
    """Visible SharePoint list fields plus a compact preview string."""

    item_id: GraphId
    web_url: OptionalUrl
    created_date_time: OptionalDateTime
    last_modified_date_time: OptionalDateTime
    fields: Annotated[
        JsonObject,
        Field(description="Visible field values returned by Microsoft Graph."),
    ]
    text_preview: Annotated[
        str,
        Field(
            description="A compact human-readable preview built from visible fields."
        ),
    ]


class PageMetadata(BaseModel):
    """Normalized metadata describing a modern SharePoint page."""

    page_id: GraphId
    title: Annotated[Optional[str], Field(description="The page title.", default=None)]
    name: Annotated[
        Optional[str], Field(description="The page file name.", default=None)
    ]
    page_layout: Annotated[
        Optional[str], Field(description="The modern page layout.", default=None)
    ]
    promotion_kind: Annotated[
        Optional[str], Field(description="The page promotion kind.", default=None)
    ]
    web_url: OptionalUrl
    created_date_time: OptionalDateTime
    last_modified_date_time: OptionalDateTime


class DriveItemMetadata(BaseModel):
    """Normalized metadata describing a SharePoint drive file or folder."""

    item_id: GraphId
    name: Annotated[Optional[str], Field(description="The item name.", default=None)]
    item_type: Annotated[
        Literal["file", "folder", "package", "unknown"],
        Field(description="The normalized drive item type."),
    ]
    web_url: OptionalUrl
    mime_type: Annotated[
        Optional[str],
        Field(description="The file MIME type, for file items.", default=None),
    ]
    size: Annotated[
        Optional[int],
        Field(description="The item size in bytes, when provided.", default=None),
    ]
    child_count: Annotated[
        Optional[int],
        Field(description="Folder child count, for folder items.", default=None),
    ]
    parent_reference: Annotated[
        Optional[JsonObject],
        Field(description="Parent reference metadata from Graph.", default=None),
    ]
    created_date_time: OptionalDateTime
    last_modified_date_time: OptionalDateTime
    created_by: Annotated[
        Optional[str], Field(description="Creator display name or email.", default=None)
    ]
    last_modified_by: Annotated[
        Optional[str],
        Field(description="Last modifier display name or email.", default=None),
    ]


class SearchSharePointSitesRequest(BaseRequest):
    """Request model for searching SharePoint sites visible to the user."""

    query: Annotated[
        str,
        Field(
            description="Site search query, such as a project or department name.",
            min_length=1,
        ),
    ]
    page: PageNumber
    use_cache: UseCache

    @field_validator("query", mode="before")
    @classmethod
    def cleanse_query(cls, value: object) -> object:
        """
        Removes quote characters that can break Microsoft Graph search syntax.

        Args:
            value: object -> The raw query value.

        Returns:
            object -> The cleansed query value.
        """
        if isinstance(value, str):
            return re.sub(r"['\"]+", " ", value).strip()
        return value

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for the site search.

        Args:
            None

        Returns:
            str -> The endpoint path with encoded search query.
        """
        return f"/sites?search={quote(self.query, safe='')}"


class SearchSharePointSitesResponse(PaginatedResponse):
    """Response model for searching SharePoint sites."""

    sites: Annotated[
        list[SiteMetadata],
        Field(description="Matching SharePoint sites returned by Microsoft Graph."),
    ]


class GetSharePointSiteRequest(BaseRequest):
    """Request model for reading SharePoint site metadata."""

    site_id: GraphId

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for one SharePoint site.

        Args:
            None

        Returns:
            str -> The site metadata endpoint path.
        """
        return f"/sites/{quote(self.site_id, safe=',:')}"


class GetSharePointSiteResponse(BaseResponse):
    """Response model for reading SharePoint site metadata."""

    site: Annotated[
        Optional[SiteMetadata],
        Field(description="Expanded SharePoint site metadata.", default=None),
    ]


class DiscoverSharePointSiteContentRequest(BaseRequest):
    """Request model for one-call SharePoint site content discovery."""

    site_id: GraphId
    include_document_libraries: Annotated[
        bool,
        Field(description="Whether to include document-library drives.", default=True),
    ]
    include_lists: Annotated[
        bool,
        Field(description="Whether to include SharePoint lists.", default=True),
    ]
    include_pages: Annotated[
        bool,
        Field(description="Whether to include modern SharePoint pages.", default=True),
    ]
    use_cache: UseCache


class DiscoverSharePointSiteContentResponse(BaseResponse):
    """Response model for one-call SharePoint site content discovery."""

    site: Annotated[
        Optional[SiteMetadata],
        Field(description="The requested SharePoint site metadata.", default=None),
    ]
    document_libraries: Annotated[
        list[DriveMetadata],
        Field(
            description="Document-library drives available in the site.",
            default_factory=list,
        ),
    ]
    lists: Annotated[
        list[SharePointListMetadata],
        Field(
            description="SharePoint lists available in the site.", default_factory=list
        ),
    ]
    pages: Annotated[
        list[PageMetadata],
        Field(
            description="Modern SharePoint pages available in the site.",
            default_factory=list,
        ),
    ]


class ListSharePointSiteDrivesRequest(BaseRequest):
    """Request model for listing document-library drives in a site."""

    site_id: GraphId
    page: PageNumber
    use_cache: UseCache

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for document-library drives.

        Args:
            None

        Returns:
            str -> The site drives endpoint path.
        """
        return f"/sites/{quote(self.site_id, safe=',:')}/drives"


class ListSharePointSiteDrivesResponse(PaginatedResponse):
    """Response model for listing document-library drives in a site."""

    drives: Annotated[
        list[DriveMetadata],
        Field(description="Document-library drives available in the site."),
    ]


class ListSharePointSiteListsRequest(BaseRequest):
    """Request model for listing SharePoint lists in a site."""

    site_id: GraphId
    page: PageNumber
    use_cache: UseCache

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for SharePoint lists.

        Args:
            None

        Returns:
            str -> The site lists endpoint path.
        """
        return f"/sites/{quote(self.site_id, safe=',:')}/lists"


class ListSharePointSiteListsResponse(PaginatedResponse):
    """Response model for listing SharePoint lists in a site."""

    lists: Annotated[
        list[SharePointListMetadata],
        Field(description="SharePoint lists available in the site."),
    ]


class ListSharePointListItemsRequest(BaseRequest):
    """Request model for reading visible field values from a SharePoint list."""

    site_id: GraphId
    list_id: GraphId
    page: PageNumber
    use_cache: UseCache

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for SharePoint list items.

        Args:
            None

        Returns:
            str -> The list-items endpoint with visible field expansion.
        """
        return (
            f"/sites/{quote(self.site_id, safe=',:')}/lists/"
            f"{quote(self.list_id, safe=',:')}/items?expand=fields"
        )


class ListSharePointListItemsResponse(PaginatedResponse):
    """Response model for reading SharePoint list items."""

    items: Annotated[
        list[ListItemPreview],
        Field(description="SharePoint list items and compact text previews."),
    ]


class ListSharePointSitePagesRequest(BaseRequest):
    """Request model for listing modern SharePoint pages in a site."""

    site_id: GraphId
    page: PageNumber
    use_cache: UseCache

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for modern SharePoint pages.

        Args:
            None

        Returns:
            str -> The modern pages endpoint path.
        """
        return f"/sites/{quote(self.site_id, safe=',:')}/pages/microsoft.graph.sitePage"


class ListSharePointSitePagesResponse(PaginatedResponse):
    """Response model for listing modern SharePoint pages in a site."""

    pages: Annotated[
        list[PageMetadata],
        Field(description="Modern SharePoint pages returned by Microsoft Graph."),
    ]


class GetSharePointSitePageRequest(BaseRequest):
    """Request model for reading text from a modern SharePoint page."""

    site_id: GraphId
    page_id: GraphId

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for reading an expanded site page.

        Args:
            None

        Returns:
            str -> The expanded modern site page endpoint path.
        """
        return (
            f"/sites/{quote(self.site_id, safe=',:')}/pages/"
            f"{quote(self.page_id, safe=',:')}/microsoft.graph.sitePage?expand=canvasLayout"
        )


class GetSharePointSitePageResponse(BaseResponse):
    """Response model for reading text from a modern SharePoint page."""

    page: Annotated[
        Optional[PageMetadata],
        Field(description="The page metadata.", default=None),
    ]
    text: Annotated[
        str,
        Field(description="Readable text extracted from the page payload.", default=""),
    ]
    text_char_count: Annotated[
        int,
        Field(
            description="Number of characters returned in the text field.",
            ge=0,
            default=0,
        ),
    ]


class ListSharePointDriveItemsRequest(BaseRequest):
    """Request model for listing files and folders in a SharePoint document library."""

    drive_id: GraphId
    parent_item_id: Annotated[
        Optional[str],
        Field(
            description="Optional folder item ID whose children should be listed.",
            min_length=1,
            default=None,
        ),
    ]
    root_relative_path: Annotated[
        Optional[str],
        Field(
            description="Optional root-relative folder path whose children should be listed.",
            min_length=1,
            default=None,
        ),
    ]
    page: PageNumber
    use_cache: UseCache

    @model_validator(mode="after")
    def validate_single_location(self) -> Self:
        """
        Ensures callers identify at most one folder location.

        Args:
            None

        Returns:
            Self -> The validated request.
        """
        if self.parent_item_id and self.root_relative_path:
            raise ValueError(
                "Provide either parent_item_id or root_relative_path, not both."
            )
        return self

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for listing drive children.

        Args:
            None

        Returns:
            str -> The drive children endpoint path.
        """
        encoded_drive_id = quote(self.drive_id, safe=",:")
        if self.parent_item_id:
            encoded_item_id = quote(self.parent_item_id, safe=",:")
            return f"/drives/{encoded_drive_id}/items/{encoded_item_id}/children"
        if self.root_relative_path:
            encoded_path = self._encode_root_relative_path(self.root_relative_path)
            if encoded_path:
                return f"/drives/{encoded_drive_id}/root:/{encoded_path}:/children"
        return f"/drives/{encoded_drive_id}/root/children"

    def _encode_root_relative_path(self, root_relative_path: str) -> str:
        """
        Encodes every segment in a root-relative SharePoint drive path.

        Args:
            root_relative_path: str -> The raw root-relative folder path.

        Returns:
            str -> A URL-encoded path safe for Microsoft Graph path addressing.
        """
        return "/".join(
            quote(segment, safe="")
            for segment in root_relative_path.strip("/").split("/")
            if segment
        )


class ListSharePointDriveItemsResponse(PaginatedResponse):
    """Response model for listing SharePoint drive items."""

    items: Annotated[
        list[DriveItemMetadata],
        Field(
            description="Files and folders in the requested document-library location."
        ),
    ]


class GetSharePointDriveItemRequest(BaseRequest):
    """Request model for reading metadata for one SharePoint drive item."""

    drive_id: GraphId
    item_id: GraphId

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for one drive item.

        Args:
            None

        Returns:
            str -> The drive item metadata endpoint path.
        """
        return (
            f"/drives/{quote(self.drive_id, safe=',:')}/items/"
            f"{quote(self.item_id, safe=',:')}"
        )


class GetSharePointDriveItemResponse(BaseResponse):
    """Response model for reading metadata for one SharePoint drive item."""

    item: Annotated[
        Optional[DriveItemMetadata],
        Field(description="The requested drive item metadata.", default=None),
    ]


class SearchSharePointDriveItemsRequest(BaseRequest):
    """Request model for searching a SharePoint document-library drive."""

    drive_id: GraphId
    query: Annotated[
        str,
        Field(description="File or folder search query.", min_length=1),
    ]
    page: PageNumber
    use_cache: UseCache

    @field_validator("query", mode="before")
    @classmethod
    def cleanse_query(cls, value: object) -> object:
        """
        Removes punctuation that can break the Graph drive search route.

        Args:
            value: object -> The raw query value.

        Returns:
            object -> The cleansed query value.
        """
        if isinstance(value, str):
            return re.sub(r"[\/'\"]+", " ", value).strip()
        return value

    @computed_field
    @property
    def endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for drive item search.

        Args:
            None

        Returns:
            str -> The drive search endpoint path.
        """
        encoded_query = quote(self.query, safe="")
        return f"/drives/{quote(self.drive_id, safe=',:')}/root/search(q='{encoded_query}')"


class SearchSharePointDriveItemsResponse(PaginatedResponse):
    """Response model for searching SharePoint drive items."""

    items: Annotated[
        list[DriveItemMetadata],
        Field(description="Matching files and folders in the document-library drive."),
    ]


class IngestSharePointDriveItemRequest(BaseRequest):
    """Request model for ingesting a SharePoint file into the GCS Landing Zone."""

    drive_id: GraphId
    item_id: GraphId
    use_cache: UseCache

    @computed_field
    @property
    def metadata_endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for metadata lookup before ingestion.

        Args:
            None

        Returns:
            str -> The drive item metadata endpoint path.
        """
        return (
            f"/drives/{quote(self.drive_id, safe=',:')}/items/"
            f"{quote(self.item_id, safe=',:')}"
        )

    @computed_field
    @property
    def content_endpoint(self) -> str:
        """
        Builds the Microsoft Graph endpoint for file-content streaming.

        Args:
            None

        Returns:
            str -> The drive item content endpoint path.
        """
        return f"{self.metadata_endpoint}/content"


class IngestSharePointDriveItemResponse(BaseResponse):
    """Response model returning GCS details for an ingested SharePoint file."""

    gcs_uri: Annotated[
        Optional[str],
        Field(
            description="The Google Cloud Storage URI where the file was ingested.",
            pattern=r"^gs://",
            default=None,
        ),
    ]
    mime_type: Annotated[
        Optional[str],
        Field(description="The MIME type of the ingested file.", default=None),
    ]
    filename: Annotated[
        Optional[str],
        Field(description="The original SharePoint filename.", default=None),
    ]
    inject_file_data: Annotated[
        bool,
        Field(
            description="Flag consumed by the multimodal file-injection plugin.",
            default=False,
        ),
    ]


DEFAULT_PAGE_SIZE = SHAREPOINT_SERVER_CONFIG.max_items_per_page
