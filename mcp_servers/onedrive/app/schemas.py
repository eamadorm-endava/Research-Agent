# Allows lazy evaluation of type hints, removing the need for string forward references in recursive classes
from __future__ import annotations
from typing import Annotated, Literal, Optional, Self, Union
import re
from enum import StrEnum
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator
from .config import MainFolder


# --- Reusable Type Aliases ---
class SortByOption(StrEnum):
    NAME = "name"
    CREATION_DATE = "creation_date"
    LAST_MODIFIED_DATE = "last_modified_date"


class SortOrderOption(StrEnum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class ObjectTypeOption(StrEnum):
    FILE = "file"
    FOLDER = "folder"


SortBy = Annotated[
    Optional[SortByOption],
    Field(
        description="Sorting criteria.",
        default=None,
    ),
]

SortOrder = Annotated[
    Optional[SortOrderOption],
    Field(
        description="Sorting order.",
        default=None,
    ),
]
ItemId = Annotated[
    str,
    Field(
        description="The unique identifier of the item.",
        min_length=1,
    ),
]

FileName = Annotated[
    str,
    Field(
        description="The name of the file.",
        min_length=1,
    ),
]

DateStr = Annotated[
    str,
    Field(
        description="A date string in 'YYYY-MM-DD' format.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
]

PageNumber = Annotated[
    int,
    Field(
        description="The page number for fetching paginated results (1-indexed).",
        ge=1,
        default=1,
    ),
]

UseCache = Annotated[
    bool,
    Field(
        description="Set to False only to force a cache reload if you expect newly uploaded/updated files. Otherwise, leave True.",
        default=True,
    ),
]


# --- Base Models ---
class SessionContext(BaseModel):
    """Dependencies injected by the framework for the current session context."""

    app_name: Annotated[
        str,
        Field(
            description="The name of the calling application or agent.",
            min_length=1,
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
        Field(
            description="The current session or conversation ID with the agent.",
            min_length=1,
        ),
    ]


class BaseRequest(BaseModel):
    """Base class for all requests requiring agent dependencies to prevent LLM hallucination."""

    dependencies: Annotated[
        Optional[SessionContext],
        Field(
            default=None,
            exclude=True,
            description="Parameters injected by the framework. The LLM will not see this to avoid hallucinations.",
        ),
    ]


class BaseResponse(BaseModel):
    """Base class for all responses containing standard execution status fields."""

    execution_status: Annotated[
        Literal["success", "error"],
        Field(
            description="The status of the tool execution.",
            default="success",
        ),
    ]
    execution_message: Annotated[
        str,
        Field(
            description="A descriptive message about the execution result.",
            default="Tool executed successfully.",
        ),
    ]


class BasePaginatedResponse(BaseModel):
    """Base class for responses returning paginated lists of files and folders."""

    total_pages: Annotated[
        int,
        Field(
            description="Total number of pages available.",
            ge=1,
        ),
    ]
    current_page: Annotated[
        int,
        Field(description="The current page number shown.", ge=1),
    ]
    items_in_page: Annotated[
        int,
        Field(
            description="Number of items returned in this specific page slice.",
            ge=0,
        ),
    ]
    objects_found: Annotated[
        list[Union[FileMetadata, FolderMetadata]],
        Field(
            description="List of file and folder objects representing the results.",
        ),
    ]


class BaseDateFilterRequest(BaseModel):
    """Base class for requests that filter by creation or modified date ranges."""

    min_creation_date: Annotated[
        Optional[DateStr],
        Field(
            description="Optional minimum creation date (e.g., '2023-10-25').",
            default=None,
        ),
    ]
    max_creation_date: Annotated[
        Optional[DateStr],
        Field(
            description="Optional maximum creation date (e.g., '2023-10-25').",
            default=None,
        ),
    ]
    min_last_modified_date: Annotated[
        Optional[DateStr],
        Field(
            description="Optional minimum last modified date (e.g., '2023-10-25').",
            default=None,
        ),
    ]
    max_last_modified_date: Annotated[
        Optional[DateStr],
        Field(
            description="Optional maximum last modified date (e.g., '2023-10-25').",
            default=None,
        ),
    ]

    @model_validator(mode="after")
    def check_created_date_window(self) -> Self:
        """
        Validates that both min and max creation dates are provided together and are logically ordered.
        Used to prevent invalid date range queries.

        Args:
            None

        Returns:
            Self -> The validated model instance.
        """
        if bool(self.min_creation_date) != bool(self.max_creation_date):
            raise ValueError(
                "Both min_creation_date and max_creation_date must be provided together."
            )
        if self.min_creation_date and self.max_creation_date:
            if self.min_creation_date > self.max_creation_date:
                raise ValueError(
                    "min_creation_date cannot be later than max_creation_date."
                )
        return self

    @model_validator(mode="after")
    def check_modified_date_window(self) -> Self:
        """
        Validates that both min and max modified dates are provided together and are logically ordered.
        Used to prevent invalid date range queries.

        Args:
            None

        Returns:
            Self -> The validated model instance.
        """
        if bool(self.min_last_modified_date) != bool(self.max_last_modified_date):
            raise ValueError(
                "Both min_last_modified_date and max_last_modified_date must be provided together."
            )
        if self.min_last_modified_date and self.max_last_modified_date:
            if self.min_last_modified_date > self.max_last_modified_date:
                raise ValueError(
                    "min_last_modified_date cannot be later than max_last_modified_date."
                )
        return self


# --- Object Metadata Models (Recursive Tree) ---
class ObjectMetadata(BaseModel):
    """Abstract base class for all file and folder items."""

    object_name: FileName
    creation_date: Annotated[
        Optional[str],
        Field(
            description="Creation time of the object in ISO 8601 format.", default=None
        ),
    ]
    update_date: Annotated[
        Optional[str],
        Field(description="Last modified time of the object.", default=None),
    ]
    owner: Annotated[
        Optional[str],
        Field(description="Owner of the object, if available.", default=None),
    ]
    folder_path: Annotated[
        str, Field(description="Absolute path of the object inside OneDrive.")
    ]
    url: Annotated[
        Optional[str],
        Field(
            description="Web URL to access the object.",
            pattern=r"^https?://",
            default=None,
        ),
    ]
    object_type: Annotated[
        ObjectTypeOption,
        Field(description="Discriminator type indicating if this is a file or folder."),
    ]


class FileMetadata(ObjectMetadata):
    """Metadata representing a single file in OneDrive."""

    object_type: Literal[ObjectTypeOption.FILE] = ObjectTypeOption.FILE
    file_id: Annotated[
        Optional[ItemId],
        Field(
            description="Unique identifier of the file.",
            default=None,
        ),
    ]
    mime_type: Annotated[
        Optional[str], Field(description="MIME type of the file.", default=None)
    ]


class FolderMetadata(ObjectMetadata):
    """Metadata representing a folder in OneDrive, containing nested children."""

    object_type: Literal[ObjectTypeOption.FOLDER] = ObjectTypeOption.FOLDER
    folder_id: Annotated[
        Optional[ItemId],
        Field(
            description="Unique identifier of the folder. Can be None if the folder is structurally synthesized.",
            default=None,
        ),
    ]
    total_items_in_folder: Annotated[
        Optional[int],
        Field(
            description="Total number of items matching the query in this folder.",
            ge=0,
            default=None,
        ),
    ]
    total_pages_in_folder: Annotated[
        Optional[int],
        Field(
            description="Total number of pages available for this folder.",
            ge=1,
            default=None,
        ),
    ]
    current_page: Annotated[
        Optional[int],
        Field(description="The current page number shown.", ge=1, default=None),
    ]
    items_in_page: Annotated[
        Optional[int],
        Field(
            description="Number of items returned in this specific page slice.",
            ge=0,
            default=None,
        ),
    ]
    child_objects: Annotated[
        Optional[list[Union[FileMetadata, FolderMetadata]]],
        Field(
            description="Nested files and subfolders within this folder.", default=None
        ),
    ]


# --- Tool Request / Response Models ---
class FindItemsRequest(BaseRequest, BaseDateFilterRequest):
    """Request model for finding items globally across OneDrive with pagination."""

    main_folder: Annotated[
        MainFolder,
        Field(
            description="The main OneDrive space to search within",
            default=MainFolder.MY_FILES,
        ),
    ]

    item_name: Annotated[
        Optional[str],
        Field(
            description="Optional item name to filter by.",
            min_length=1,
            default=None,
        ),
    ]

    sort_by: SortBy
    sort_order: SortOrder
    page: PageNumber
    use_cache: UseCache

    @field_validator("item_name", mode="after")
    @classmethod
    def cleanse_search_terms(cls, value: Optional[str]) -> Optional[str]:
        """
        Cleanses search terms by replacing unescaped slashes and quotes with spaces.
        Reason: Microsoft Graph API will crash with a 400 Bad Request if slashes are sent
        in the raw query string. This validator protects the API.

        Args:
            value: Optional[str] -> The raw string value.

        Returns:
            Optional[str] -> The cleansed string value.
        """
        if value:
            return re.sub(r"[\/\\\'\"]+", " ", value).strip()
        return value

    @computed_field
    @property
    def item_name_tokens(self) -> list[str]:
        """
        Tokenizes the item name for fuzzy matching.
        Reason: Extracts tokenization logic out of the client and into the schema
        so the client only has to loop over pre-computed arrays.

        Args:
            None

        Returns:
            list[str] -> List of fuzzy match tokens.
        """
        if not self.item_name:
            return []
        return [
            token for token in re.split(r"[\s\-_/\\]+", self.item_name.lower()) if token
        ]


class FindItemsResponse(BaseResponse, BasePaginatedResponse):
    """Response model returning paginated global search results grouped by folders."""

    execution_message: Annotated[
        str,
        Field(
            description="A descriptive message about the execution result.",
            default="Tool executed successfully. NOTE: The returned files ONLY reflect items matching the requested filters.",
        ),
    ]
    total_search_matches: Annotated[
        int,
        Field(
            description="Total number of root items matching the global search query.",
            ge=0,
        ),
    ]


class ListFolderContentsRequest(BaseRequest, BaseDateFilterRequest):
    """Request model for listing exact contents of a specific folder."""

    folder_id: ItemId
    page: PageNumber
    use_cache: UseCache
    sort_by: SortBy
    sort_order: SortOrder


class ListFolderContentsResponse(BaseResponse, BasePaginatedResponse):
    """Response model returning paginated files explicitly within a specific folder."""

    total_items_in_folder: Annotated[
        int,
        Field(
            description="Total number of items in this folder.",
            ge=0,
        ),
    ]


class ReadFileRequest(BaseRequest):
    """Request model for reading and ingesting a specific file by ID."""

    file_id: ItemId
    use_cache: Annotated[
        bool,
        Field(
            description="If True, skips uploading to GCS if the exact file was successfully ingested in the last few minutes, returning the cached GCS URI instantly.",
            default=True,
        ),
    ]


class ReadFileResponse(BaseResponse):
    """Response model returning GCS details for a read/ingested file."""

    gcs_uri: Annotated[
        Optional[str],
        Field(
            description="The Google Cloud Storage URI where the file was ingested. Will be None if execution failed.",
            pattern=r"^gs://",
            default=None,
        ),
    ]
    mime_type: Annotated[
        Optional[str],
        Field(
            description="The MIME type of the file. Will be None if execution failed.",
            default=None,
        ),
    ]
    filename: Annotated[
        Optional[str],
        Field(
            description="The name of the file. Will be None if execution failed.",
            default=None,
        ),
    ]
    inject_file_data: Annotated[
        bool,
        Field(
            description="Flag to trigger multimodal file injection.",
            default=False,
        ),
    ]
