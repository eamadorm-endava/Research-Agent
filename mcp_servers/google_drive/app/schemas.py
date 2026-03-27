from enum import StrEnum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuthenticationError(Exception):
    """Raised when OAuth token validation fails."""

    pass


class DriveSchemaModel(BaseModel):
    """Shared schema base for the Google Drive MCP server."""

    model_config = ConfigDict(extra="forbid")


class DriveMimeType(StrEnum):
    """Common Drive-compatible MIME types exposed to the agent."""

    GOOGLE_DOC = "application/vnd.google-apps.document"
    GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
    GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
    GOOGLE_FOLDER = "application/vnd.google-apps.folder"
    PDF = "application/pdf"
    PLAIN_TEXT = "text/plain"
    WORD_DOCX = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    EXCEL_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    POWERPOINT_PPTX = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    PNG_IMAGE = "image/png"


class SortDirection(StrEnum):
    """Supported sort directions for list operations."""

    ASC = "asc"
    DESC = "desc"


class ListFilesSortField(StrEnum):
    """Supported sortable fields for Drive listing operations."""

    FOLDER_NAME = "folder_name"
    FILE_NAME = "file_name"
    CREATION_TIME = "creation_time"
    LAST_UPDATE = "last_update"


EXECUTION_STATUS = Annotated[
    Literal["success", "error"],
    Field(description="Whether the tool completed successfully."),
]
EXECUTION_MESSAGE = Annotated[
    str,
    Field(
        default="Execution completed successfully.",
        description="Details about the execution or the encountered error.",
    ),
]
MAX_RESULTS = Annotated[
    int,
    Field(
        default=10,
        description="Maximum number of items to return.",
        ge=1,
        le=1000,
    ),
]
FOLDER_ID = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Optional Drive folder ID to restrict results or place new items into.",
    ),
]
DESTINATION_FOLDER_ID = Annotated[
    str,
    Field(
        min_length=1, description="Destination Drive folder ID for a move operation."
    ),
]
DRIVE_FILE_ID = Annotated[
    str,
    Field(min_length=1, description="Drive file or folder ID."),
]
MAX_CHARS = Annotated[
    int,
    Field(
        default=60000,
        ge=1,
        le=1_000_000,
        description="Maximum number of characters to return from extracted text.",
    ),
]
DOCUMENT_TITLE = Annotated[
    str,
    Field(min_length=1, max_length=250, description="Human-readable Drive file title."),
]
DOCUMENT_CONTENT = Annotated[
    str,
    Field(min_length=1, description="Text content provided by the caller."),
]
PDF_TEXT_CONTENT = Annotated[
    str,
    Field(min_length=1, description="Text content to place into the PDF."),
]
GENERIC_FILE_CONTENT = Annotated[
    str,
    Field(default="", description="UTF-8 text content to store in the created file."),
]
GENERIC_FILE_MIME_TYPE = Annotated[
    str,
    Field(
        default="text/plain",
        description="MIME type to use when creating a generic file.",
    ),
]
DRIVE_FILE_NAME = Annotated[
    str,
    Field(description="Display name of the file or folder."),
]
DRIVE_FILE_MIME_TYPE = Annotated[
    str,
    Field(description="Drive MIME type."),
]
DRIVE_FILE_MODIFIED_TIME = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Last modified time in RFC 3339 format, when available.",
    ),
]
DRIVE_FILE_CREATED_TIME = Annotated[
    Optional[str],
    Field(
        default=None, description="Creation time in RFC 3339 format, when available."
    ),
]
DRIVE_FILE_WEB_VIEW_LINK = Annotated[
    Optional[str],
    Field(default=None, description="Browser URL for the file."),
]
DRIVE_FILE_SIZE = Annotated[
    Optional[int],
    Field(default=None, ge=0, description="File size in bytes, when available."),
]
DRIVE_FILE_PARENTS = Annotated[
    list[str],
    Field(default_factory=list, description="List of parent folder IDs for the file."),
]
DRIVE_FILE_VERSION = Annotated[
    Optional[int],
    Field(default=None, ge=0, description="Drive file version, when available."),
]
DRIVE_FILE_PATH = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Synthetic absolute Drive path resolved from the parent chain, for example /Documents/Project/notes.txt.",
    ),
]
OWNER_DISPLAY_NAME = Annotated[
    Optional[str],
    Field(default=None, description="Display name of the file owner."),
]
OWNER_EMAIL_ADDRESS = Annotated[
    Optional[str],
    Field(default=None, description="Email address of the file owner."),
]
NEW_NAME = Annotated[
    str,
    Field(
        min_length=1,
        max_length=250,
        description="New display name for the file or folder.",
    ),
]
DRIVE_DOCUMENT_TEXT = Annotated[
    str,
    Field(default="", description="Extracted text content."),
]
FOLDER_PATH_FILTER = Annotated[
    Optional[str],
    Field(
        default=None,
        pattern=r"^(?:[\w\s-]+(?:/[\w\s-]+)*)/?$",
        description="Folder path filter using slash-separated folder names, for example Documents/Project/.",
    ),
]
FILE_NAME_FILTER = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Case-insensitive file name filter. Partial matches are allowed.",
    ),
]
LIST_MIME_TYPE_FILTER = Annotated[
    Optional[DriveMimeType],
    Field(default=None, description="Optional MIME type filter for the listed items."),
]
DATE_FILTER = Annotated[
    Optional[str],
    Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description='Date filter in the format "YYYY-MM-DD".',
    ),
]
LIST_ORDER_BY = Annotated[
    dict[ListFilesSortField, SortDirection],
    Field(
        default_factory=dict,
        description='Sort directives, for example {"file_name": "asc", "last_update": "desc"}.',
    ),
]
TOTAL_FILES = Annotated[
    int,
    Field(
        default=0,
        ge=0,
        description="Total number of non-folder items that matched the filter set.",
    ),
]
TOTAL_FOLDERS = Annotated[
    int,
    Field(
        default=0,
        ge=0,
        description="Total number of folders that matched the filter set.",
    ),
]
FOLDER_PATH = Annotated[
    str,
    Field(
        default="/",
        description="Resolved folder path that contains the file or folder.",
    ),
]
FILE_IDENTIFIER = Annotated[str, Field(description="Drive file identifier.")]
CREATED_AT = Annotated[
    Optional[str],
    Field(default=None, description="Creation timestamp in RFC 3339 format."),
]
LAST_UPDATE_AT = Annotated[
    Optional[str],
    Field(default=None, description="Last update timestamp in RFC 3339 format."),
]
MIME_TYPE_OUTPUT = Annotated[str, Field(description="MIME type of the file or folder.")]


class BaseResponse(DriveSchemaModel):
    """Common response fields for all tool executions."""

    execution_status: EXECUTION_STATUS
    execution_message: EXECUTION_MESSAGE


class DriveOwnerModel(DriveSchemaModel):
    """Owner metadata included in Drive file responses."""

    displayName: OWNER_DISPLAY_NAME
    emailAddress: OWNER_EMAIL_ADDRESS


DRIVE_FILE_OWNERS = Annotated[
    list[DriveOwnerModel],
    Field(default_factory=list, description="Owners of the file, when available."),
]


class DriveFileModel(DriveSchemaModel):
    """Metadata for a single Google Drive file or folder."""

    id: DRIVE_FILE_ID
    name: DRIVE_FILE_NAME
    mimeType: DRIVE_FILE_MIME_TYPE
    modifiedTime: DRIVE_FILE_MODIFIED_TIME
    createdTime: DRIVE_FILE_CREATED_TIME
    webViewLink: DRIVE_FILE_WEB_VIEW_LINK
    size: DRIVE_FILE_SIZE
    parents: DRIVE_FILE_PARENTS
    owners: DRIVE_FILE_OWNERS
    version: DRIVE_FILE_VERSION
    path: DRIVE_FILE_PATH


class DriveDocumentModel(DriveFileModel):
    """Extended file metadata including extracted text content."""

    text: DRIVE_DOCUMENT_TEXT


class FileCreatorModel(DriveSchemaModel):
    """Normalized creator information for list results."""

    name: Annotated[
        Optional[str],
        Field(default=None, description="Display name of the creator/owner."),
    ]
    email: Annotated[
        Optional[str], Field(default=None, description="Email of the creator/owner.")
    ]


class DriveFileMetadata(DriveSchemaModel):
    """Compact Drive metadata tailored for list_files responses."""

    creation_at: CREATED_AT
    last_update_at: LAST_UPDATE_AT
    folder_path: FOLDER_PATH
    file_name: DRIVE_FILE_NAME
    file_id: FILE_IDENTIFIER
    created_by: FileCreatorModel
    mime_type: MIME_TYPE_OUTPUT


DRIVE_FILE_LIST = Annotated[
    list[DriveFileModel],
    Field(default_factory=list, description="List of file metadata objects."),
]
LIST_FILE_METADATA = Annotated[
    list[DriveFileMetadata],
    Field(
        default_factory=list,
        description="List of filtered Drive file metadata results.",
    ),
]
DRIVE_FILE = Annotated[
    Optional[DriveFileModel],
    Field(default=None, description="Drive file metadata returned by the operation."),
]
DRIVE_DOCUMENT = Annotated[
    Optional[DriveDocumentModel],
    Field(
        default=None,
        description="Drive document metadata plus extracted text.",
    ),
]


class ListFilesRequest(DriveSchemaModel):
    """Request schema for listing files with rich Drive filters."""

    folder_name: FOLDER_PATH_FILTER
    file_name: FILE_NAME_FILTER
    mime_type: LIST_MIME_TYPE_FILTER
    creation_time: DATE_FILTER
    last_update: DATE_FILTER
    order_by: LIST_ORDER_BY
    max_results: MAX_RESULTS


class ListFilesResponse(BaseResponse):
    """Response schema containing filtered Drive listing results."""

    total_files: TOTAL_FILES
    total_folders: TOTAL_FOLDERS
    files: LIST_FILE_METADATA


class GetFileTextRequest(DriveSchemaModel):
    """Request schema for extracting text from a file."""

    file_id: DRIVE_FILE_ID
    max_chars: MAX_CHARS


class GetFileTextResponse(GetFileTextRequest, BaseResponse):
    """Response schema containing the extracted document text."""

    document: DRIVE_DOCUMENT


class CreateGoogleDocRequest(DriveSchemaModel):
    """Request schema for creating a new Google Doc."""

    title: DOCUMENT_TITLE
    content: DOCUMENT_CONTENT
    folder_id: FOLDER_ID


class CreateGoogleDocResponse(CreateGoogleDocRequest, BaseResponse):
    """Response schema for a created Google Doc."""

    file: DRIVE_FILE


class UploadPdfRequest(DriveSchemaModel):
    """Request schema for creating a PDF from text."""

    title: DOCUMENT_TITLE
    text: PDF_TEXT_CONTENT
    folder_id: FOLDER_ID


class UploadPdfResponse(UploadPdfRequest, BaseResponse):
    """Response schema for an uploaded PDF."""

    file: DRIVE_FILE


class CreateFileRequest(DriveSchemaModel):
    """Request schema for creating a generic text-based file."""

    name: DOCUMENT_TITLE
    content: GENERIC_FILE_CONTENT
    mime_type: GENERIC_FILE_MIME_TYPE
    folder_id: FOLDER_ID


class CreateFileResponse(CreateFileRequest, BaseResponse):
    """Response schema for a created generic file."""

    file: DRIVE_FILE


class CreateFolderRequest(DriveSchemaModel):
    """Request schema for creating a Google Drive folder."""

    name: DOCUMENT_TITLE
    folder_id: FOLDER_ID


class CreateFolderResponse(CreateFolderRequest, BaseResponse):
    """Response schema for a created folder."""

    file: DRIVE_FILE


class MoveFileRequest(DriveSchemaModel):
    """Request schema for moving an existing file or folder."""

    file_id: DRIVE_FILE_ID
    destination_folder_id: DESTINATION_FOLDER_ID


class MoveFileResponse(MoveFileRequest, BaseResponse):
    """Response schema for a moved Drive item."""

    file: DRIVE_FILE


class RenameFileRequest(DriveSchemaModel):
    """Request schema for renaming a file or folder."""

    file_id: DRIVE_FILE_ID
    new_name: NEW_NAME


class RenameFileResponse(RenameFileRequest, BaseResponse):
    """Response schema for a renamed Drive item."""

    file: DRIVE_FILE
