from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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
    Optional[str],
    Field(default=None, description="Optional Drive folder ID to restrict results."),
]
OPTIONAL_MIME_TYPES = Annotated[
    Optional[list[str]],
    Field(
        default=None,
        description="Optional list of MIME types to include in search results.",
    ),
]


class BaseResponse(BaseModel):
    execution_status: Annotated[
        Literal["success", "error"],
        Field(description="Whether the tool completed successfully."),
    ]
    execution_message: Annotated[
        str,
        Field(
            default="Execution completed successfully.",
            description="Details about the execution or the encountered error.",
        ),
    ]


class DriveFileModel(BaseModel):
    id: str = Field(description="Drive file ID.")
    name: str = Field(description="Display name of the file.")
    mimeType: str = Field(description="Drive MIME type.")
    modifiedTime: str | None = Field(default=None, description="Last modified time.")
    webViewLink: str | None = Field(default=None, description="Browser URL for the file.")


class DriveDocumentModel(DriveFileModel):
    text: str = Field(description="Extracted text content.")


class ListFilesRequest(BaseModel):
    max_results: MAX_RESULTS = 10
    folder_id: OPTIONAL_FOLDER_ID = None
    include_folders: bool = Field(
        default=False,
        description="Whether folders should be included in the result set.",
    )


class ListFilesResponse(ListFilesRequest, BaseResponse):
    files: list[DriveFileModel] = Field(
        default_factory=list,
        description="List of file metadata objects.",
    )


class SearchFilesRequest(BaseModel):
    search_text: str | None = Field(
        default=None,
        description="Plain-text search term used against name/fullText.",
    )
    drive_query: str | None = Field(
        default=None,
        description="Raw Drive query-language expression. If provided, this takes precedence.",
    )
    max_results: MAX_RESULTS = 10
    folder_id: OPTIONAL_FOLDER_ID = None
    include_folders: bool = Field(default=False)
    mime_types: OPTIONAL_MIME_TYPES = None

    @model_validator(mode="after")
    def validate_query(self) -> "SearchFilesRequest":
        if not (self.search_text or self.drive_query):
            raise ValueError("Either search_text or drive_query must be provided.")
        return self


class SearchFilesResponse(SearchFilesRequest, BaseResponse):
    files: list[DriveFileModel] = Field(default_factory=list)


class GetFileTextRequest(BaseModel):
    file_id: str = Field(min_length=1, description="Drive file ID to fetch.")
    max_chars: int = Field(
        default=60000,
        ge=1,
        le=1_000_000,
        description="Maximum number of characters to return from extracted text.",
    )


class GetFileTextResponse(GetFileTextRequest, BaseResponse):
    document: DriveDocumentModel | None = Field(
        default=None,
        description="Drive document metadata plus extracted text.",
    )


class CreateGoogleDocRequest(BaseModel):
    title: str = Field(min_length=1, max_length=250, description="Name of the Google Doc.")
    content: str = Field(min_length=1, description="Text content to insert into the doc.")
    folder_id: OPTIONAL_FOLDER_ID = None


class CreateGoogleDocResponse(CreateGoogleDocRequest, BaseResponse):
    file: DriveFileModel | None = Field(default=None)


class UploadPdfRequest(BaseModel):
    title: str = Field(min_length=1, max_length=250, description="Base name of the PDF file.")
    text: str = Field(min_length=1, description="Text content to place into the PDF.")
    folder_id: OPTIONAL_FOLDER_ID = None


class UploadPdfResponse(UploadPdfRequest, BaseResponse):
    file: DriveFileModel | None = Field(default=None)
