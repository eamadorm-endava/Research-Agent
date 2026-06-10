from typing import Annotated, Literal, Optional, Self, Union
import re
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator
from .config import MainFolder

# --- Reusable Type Aliases ---
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

MimeTypeStr = Annotated[
    str,
    Field(
        description="The MIME type of the file.",
    ),
]


# --- Base Models ---
class AgentDependencies(BaseModel):
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
        Optional[AgentDependencies],
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


# --- Object Metadata Models (Recursive Tree) ---
class ObjectMetadata(BaseModel):
    """Abstract base class for all file and folder items."""

    item_id: Annotated[
        Optional[ItemId],
        Field(
            description="Unique identifier of the object. Can be None if the folder is structurally synthesized.",
            default=None,
        ),
    ]
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
        Literal["file", "folder"],
        Field(description="Discriminator type indicating if this is a file or folder."),
    ]


class FileMetadata(ObjectMetadata):
    """Metadata representing a single file in OneDrive."""

    object_type: Literal["file"] = "file"
    mime_type: Annotated[
        Optional[MimeTypeStr], Field(description="MIME type of the file.", default=None)
    ]


class FolderMetadata(ObjectMetadata):
    """Metadata representing a folder in OneDrive, containing nested children."""

    object_type: Literal["folder"] = "folder"
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
        Optional[list[Union["FileMetadata", "FolderMetadata"]]],
        Field(
            description="Nested files and subfolders within this folder.", default=None
        ),
    ]

    @model_validator(mode="after")
    def check_pagination(self) -> Self:
        """
        Validates that the current page does not exceed the total pages.
        Used to ensure logical consistency in pagination logic.

        Args:
            None

        Returns:
            Self -> The validated model instance.
        """
        if self.current_page is not None and self.total_pages_in_folder is not None:
            if self.current_page > self.total_pages_in_folder:
                raise ValueError(
                    f"current_page ({self.current_page}) cannot exceed total_pages_in_folder ({self.total_pages_in_folder})"
                )
        return self


# --- Tool Request / Response Models ---
class SearchFilesRequest(BaseRequest):
    """Request model for searching files in OneDrive with pagination."""

    main_folder: Annotated[
        MainFolder,
        Field(
            description="The main OneDrive space to search within",
            default=MainFolder.MY_FILES,
        ),
    ]

    folder_name: Annotated[
        Optional[str],
        Field(
            description="Optional subfolder name to filter by.",
            min_length=1,
            default=None,
        ),
    ]
    file_name: Annotated[
        Optional[str],
        Field(
            description="Optional file name to filter by.",
            min_length=1,
            default=None,
        ),
    ]

    min_creation_date: Annotated[
        Optional[str],
        Field(
            description="Optional minimum creation date (e.g., '2023-10-25').",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            default=None,
        ),
    ]
    max_creation_date: Annotated[
        Optional[str],
        Field(
            description="Optional maximum creation date (e.g., '2023-10-25').",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            default=None,
        ),
    ]
    sort_by: Annotated[
        Optional[Literal["name", "creation_date", "last_modified_date"]],
        Field(
            description="Sorting criteria.",
            default="last_modified_date",
        ),
    ]
    sort_order: Annotated[
        Optional[Literal["asc", "desc"]],
        Field(
            description="Sorting order.",
            default="desc",
        ),
    ]
    page: Annotated[
        int,
        Field(
            description="Page number to retrieve (20 files per page).",
            default=1,
            ge=1,
        ),
    ]
    use_cache: Annotated[
        bool,
        Field(
            description="Set to False only to force a cache reload if you expect newly uploaded/updated files. Otherwise, leave True.",
            default=True,
        ),
    ]

    @model_validator(mode="after")
    def check_date_window(self) -> Self:
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

    @field_validator("folder_name", "file_name", mode="after")
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
    def folder_name_tokens(self) -> list[str]:
        """
        Tokenizes the folder name for fuzzy matching.
        Reason: Extracts tokenization logic out of the client and into the schema
        so the client only has to loop over pre-computed arrays.

        Args:
            None

        Returns:
            list[str] -> List of fuzzy match tokens.
        """
        if not self.folder_name:
            return []
        return [
            token
            for token in re.split(r"[\s\-_/\\]+", self.folder_name.lower())
            if token
        ]

    @computed_field
    @property
    def file_name_tokens(self) -> list[str]:
        """
        Tokenizes the file name for fuzzy matching.
        Reason: Extracts tokenization logic out of the client and into the schema
        so the client only has to loop over pre-computed arrays.

        Args:
            None

        Returns:
            list[str] -> List of fuzzy match tokens.
        """
        if not self.file_name:
            return []
        return [
            token for token in re.split(r"[\s\-_/\\]+", self.file_name.lower()) if token
        ]


class SearchFilesResponse(BaseResponse):
    """Response model returning paginated file results grouped by folders."""

    execution_message: Annotated[
        str,
        Field(
            description="A descriptive message about the execution result.",
            default="Tool executed successfully. NOTE: The returned files and pagination counts ONLY reflect items matching the requested filters. There may be other files in these folders that were excluded.",
        ),
    ]
    objects_found: Annotated[
        list[Union[FileMetadata, FolderMetadata]],
        Field(
            description="List of nested file and folder objects representing the search results.",
        ),
    ]


class ReadFileRequest(BaseRequest):
    """Request model for reading and ingesting a specific file by ID."""

    file_id: ItemId


class ReadFileResponse(BaseResponse):
    """Response model returning GCS details for a read/ingested file."""

    gcs_uri: Annotated[
        str,
        Field(
            description="The Google Cloud Storage URI where the file was ingested.",
            pattern=r"^gs://",
        ),
    ]
    mime_type: MimeTypeStr
    filename: FileName
    inject_file_data: Annotated[
        bool,
        Field(
            description="Flag to trigger multimodal file injection.",
            default=True,
        ),
    ]
