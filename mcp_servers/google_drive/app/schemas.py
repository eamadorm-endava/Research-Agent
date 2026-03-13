from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DriveSchemaModel(BaseModel):
    """Shared schema base for the Google Drive MCP server."""

    model_config = ConfigDict(extra="forbid")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


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
        le=100,
    ),
]
OPTIONAL_FOLDER_ID = Annotated[
    str | None,
    Field(default=None, description="Optional Drive folder ID to restrict results."),
]
OPTIONAL_MIME_TYPES = Annotated[
    list[str] | None,
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
    str | None,
    Field(
        default=None,
        description="Plain-text search term used against name/fullText.",
    ),
]
DRIVE_QUERY = Annotated[
    str | None,
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
    str | None,
    Field(default=None, description="Last modified time."),
]
DRIVE_FILE_WEB_VIEW_LINK = Annotated[
    str | None,
    Field(default=None, description="Browser URL for the file."),
]
DRIVE_DOCUMENT_TEXT = Annotated[
    str,
    Field(default="", description="Extracted text content."),
]


class BaseResponse(DriveSchemaModel):
    execution_status: EXECUTION_STATUS
    execution_message: EXECUTION_MESSAGE


class DriveFileModel(DriveSchemaModel):
    id: DRIVE_FILE_ID
    name: DRIVE_FILE_NAME
    mimeType: DRIVE_FILE_MIME_TYPE
    modifiedTime: DRIVE_FILE_MODIFIED_TIME
    webViewLink: DRIVE_FILE_WEB_VIEW_LINK


class DriveDocumentModel(DriveFileModel):
    text: DRIVE_DOCUMENT_TEXT


DRIVE_FILE_LIST = Annotated[
    list[DriveFileModel],
    Field(default_factory=list, description="List of file metadata objects."),
]
OPTIONAL_DRIVE_FILE = Annotated[
    DriveFileModel | None,
    Field(default=None, description="Drive file metadata returned by the operation."),
]
OPTIONAL_DRIVE_DOCUMENT = Annotated[
    DriveDocumentModel | None,
    Field(
        default=None,
        description="Drive document metadata plus extracted text.",
    ),
]


class ListFilesRequest(DriveSchemaModel):
    max_results: MAX_RESULTS
    folder_id: OPTIONAL_FOLDER_ID
    include_folders: INCLUDE_FOLDERS


class ListFilesResponse(ListFilesRequest, BaseResponse):
    files: DRIVE_FILE_LIST


class SearchFilesRequest(DriveSchemaModel):
    search_text: SEARCH_TEXT
    drive_query: DRIVE_QUERY
    max_results: MAX_RESULTS
    folder_id: OPTIONAL_FOLDER_ID
    include_folders: INCLUDE_FOLDERS
    mime_types: OPTIONAL_MIME_TYPES

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        if not (self.search_text or self.drive_query):
            raise ValueError("Either search_text or drive_query must be provided.")
        return self


class SearchFilesResponse(SearchFilesRequest, BaseResponse):
    files: DRIVE_FILE_LIST


class GetFileTextRequest(DriveSchemaModel):
    file_id: DRIVE_FILE_ID
    max_chars: MAX_CHARS


class GetFileTextResponse(GetFileTextRequest, BaseResponse):
    document: OPTIONAL_DRIVE_DOCUMENT


class CreateGoogleDocRequest(DriveSchemaModel):
    title: DOCUMENT_TITLE
    content: DOCUMENT_CONTENT
    folder_id: OPTIONAL_FOLDER_ID


class CreateGoogleDocResponse(CreateGoogleDocRequest, BaseResponse):
    file: OPTIONAL_DRIVE_FILE


class UploadPdfRequest(DriveSchemaModel):
    title: DOCUMENT_TITLE
    text: PDF_TEXT_CONTENT
    folder_id: OPTIONAL_FOLDER_ID


class UploadPdfResponse(UploadPdfRequest, BaseResponse):
    file: OPTIONAL_DRIVE_FILE
