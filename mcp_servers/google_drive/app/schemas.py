from typing import Annotated, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthenticationError(Exception):
    """Raised when OAuth token validation fails."""

    pass


class DriveSchemaModel(BaseModel):
    """Shared schema base for the Google Drive MCP server."""

    model_config = ConfigDict(extra="forbid")


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
        description="Maximum number of files to return.",
        ge=1,
        le=1000,
    ),
]
FOLDER_ID = Annotated[
    Optional[str],
    Field(default=None, description="Optional Drive folder ID to restrict results."),
]
MIME_TYPES = Annotated[
    Optional[list[str]],
    Field(
        default=None,
        description="Optional list of MIME types to include in search results.",
    ),
]
INCLUDE_FOLDERS = Annotated[
    bool,
    Field(
        default=False,
        description="Whether folders should be included in the result set.",
    ),
]
SEARCH_TEXT = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Plain-text search term used against name/fullText.",
    ),
]
DRIVE_QUERY = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Raw Drive query-language expression. If provided, this takes precedence.",
    ),
]
DRIVE_FILE_ID = Annotated[
    str,
    Field(min_length=1, description="Drive file ID."),
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
DRIVE_FILE_NAME = Annotated[
    str,
    Field(description="Display name of the file."),
]
DRIVE_FILE_MIME_TYPE = Annotated[
    str,
    Field(description="Drive MIME type."),
]
DRIVE_FILE_MODIFIED_TIME = Annotated[
    Optional[str],
    Field(default=None, description="Last modified time."),
]
DRIVE_FILE_WEB_VIEW_LINK = Annotated[
    Optional[str],
    Field(default=None, description="Browser URL for the file."),
]
DRIVE_DOCUMENT_TEXT = Annotated[
    str,
    Field(default="", description="Extracted text content."),
]


class BaseResponse(DriveSchemaModel):
    """Common response fields for all tool executions."""

    execution_status: EXECUTION_STATUS
    execution_message: EXECUTION_MESSAGE


class DriveFileModel(DriveSchemaModel):
    """Metadata for a single Google Drive file."""

    id: DRIVE_FILE_ID
    name: DRIVE_FILE_NAME
    mimeType: DRIVE_FILE_MIME_TYPE
    modifiedTime: DRIVE_FILE_MODIFIED_TIME
    webViewLink: DRIVE_FILE_WEB_VIEW_LINK


class DriveDocumentModel(DriveFileModel):
    """Extended file metadata including extracted text content."""

    text: DRIVE_DOCUMENT_TEXT


DRIVE_FILE_LIST = Annotated[
    list[DriveFileModel],
    Field(default_factory=list, description="List of file metadata objects."),
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
    """Request schema for listing files in a folder."""

    max_results: MAX_RESULTS
    folder_id: FOLDER_ID
    include_folders: INCLUDE_FOLDERS


class ListFilesResponse(ListFilesRequest, BaseResponse):
    """Response schema containing the list of files found."""

    files: DRIVE_FILE_LIST


class SearchFilesRequest(DriveSchemaModel):
    """Request schema for searching files across Drive."""

    search_text: SEARCH_TEXT
    drive_query: DRIVE_QUERY
    max_results: MAX_RESULTS
    folder_id: FOLDER_ID
    include_folders: INCLUDE_FOLDERS
    mime_types: MIME_TYPES

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        """Ensures that either search_text or drive_query is provided."""
        if not (self.search_text or self.drive_query):
            raise ValueError("Either search_text or drive_query must be provided.")
        return self


class SearchFilesResponse(SearchFilesRequest, BaseResponse):
    """Response schema containing search results."""

    files: DRIVE_FILE_LIST


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
