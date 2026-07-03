from enum import Enum
from typing import Annotated, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing_extensions import Self

# =====================================================================
# Core Infrastructure Primitives & Pagination
# =====================================================================


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class GetProfileRequest(BaseModel):
    """Request payload for retrieving the authenticated user's profile context. Requires no arguments."""

    # FastMCP uses this empty model to represent a tool parameter-less query
    pass


class GetProfileResponse(BaseModel):
    """Response payload containing the authenticated Graph account profile metrics."""

    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS
    error_message: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[str] = None


class AgentDependencies(BaseModel):
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


class BaseRequest(BaseModel):
    dependencies: Annotated[
        Optional[AgentDependencies],
        Field(
            default=None,
            exclude=True,
            description="Injected framework parameters hidden from the LLM.",
        ),
    ]

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        """
        Removes the dependencies field from the generated JSON Schema to prevent LLM hallucinations.

        Args:
            core_schema: Any -> The core Pydantic schema being processed.
            handler: Any -> The schema generation handler.

        Returns:
            dict -> The modified JSON Schema dictionary.
        """
        json_schema = super().__get_pydantic_json_schema__(core_schema, handler)
        json_schema = handler.resolve_ref_schema(json_schema)
        if "properties" in json_schema and "dependencies" in json_schema["properties"]:
            json_schema["properties"].pop("dependencies")
        return json_schema


class BaseResponse(BaseModel):
    execution_status: Annotated[
        ExecutionStatus,
        Field(description="Whether the operation succeeded or failed."),
    ] = ExecutionStatus.SUCCESS
    error_message: Annotated[
        str | None,
        Field(description="Error message when execution_status is error."),
    ] = None


class BasePaginatedResponse(BaseModel):
    current_page: Annotated[
        int, Field(default=1, description="The current page number.")
    ] = 1
    total_pages: Annotated[
        int, Field(default=1, description="Total number of pages available.")
    ] = 1
    has_next: Annotated[
        bool, Field(default=False, description="Whether a next page exists.")
    ] = False


# =====================================================================
# Reusable Enums & Sub-Models
# =====================================================================


class EmailTypeOption(str, Enum):
    SENT = "sent"
    RECEIVED = "received"
    ALL = "all"


class SortByOption(str, Enum):
    DATE = "date"
    SUBJECT = "subject"
    SENDER = "sender"


class SortOrderOption(str, Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class PersonalData(BaseModel):
    name: Annotated[
        Optional[str], Field(default=None, description="Name of the person")
    ] = None
    email: Annotated[str, Field(description="Email address of the person")]


class OutlookRecipient(BaseModel):
    email: Annotated[EmailStr, Field(description="Recipient email address.")]
    name: Annotated[
        str | None, Field(default=None, description="Optional recipient display name.")
    ] = None


class AttachmentInfo(BaseModel):
    file_name: Annotated[str, Field(description="Name of the attached file")]
    mime_type: Annotated[str, Field(description="MIME type of the file")]
    attachment_id: Annotated[str, Field(description="Unique ID of the attachment")]
    size: Annotated[int, Field(description="Size of the attachment in bytes")]


class FolderInfo(BaseModel):
    folder_id: Annotated[str, Field(description="Unique identifier for the folder")]
    display_name: Annotated[
        str, Field(description="Name of the folder (e.g., 'Inbox', 'Junk Email')")
    ]
    total_item_count: Annotated[
        int, Field(description="Total number of items in the folder")
    ]
    unread_item_count: Annotated[int, Field(description="Number of unread items")]


# =====================================================================
# Core Email Payloads
# =====================================================================


class EmailInformationPreview(BaseModel):
    email_id: Annotated[
        str, Field(description="Unique identifier for the email message")
    ]
    sender_data: Annotated[
        PersonalData, Field(description="Information about the sender")
    ]
    sent_to: Annotated[list[PersonalData], Field(description="List of recipients")]
    subject: Annotated[
        Optional[str], Field(default="", description="Email subject")
    ] = ""
    email_body_preview: Annotated[
        Optional[str],
        Field(default="", description="A short preview of the email body text"),
    ] = ""
    received_date: Annotated[
        str, Field(description="Date and time the email was received/sent")
    ]
    has_attachments: Annotated[
        bool, Field(description="True if the email has attachments")
    ] = False
    is_read: Annotated[
        bool, Field(description="True if the email has been read, False if unread")
    ] = True
    folder_name: Annotated[
        str,
        Field(
            default="Unknown Folder",
            description="Human readable name of the hosting folder",
        ),
    ] = "Unknown Folder"


class EmailInformationFull(EmailInformationPreview):
    email_body: Annotated[
        Optional[str], Field(default="", description="The complete body of the email")
    ]
    attachments: Annotated[
        list[AttachmentInfo],
        Field(default_factory=list, description="List of all attachments"),
    ]


# =====================================================================
# Tool 1: outlook_list_folders DTOs
# =====================================================================


class ListFoldersRequest(BaseRequest):
    pass


class ListFoldersResponse(BaseResponse):
    folders: Annotated[list[FolderInfo], Field(description="List of mail folders")]


# =====================================================================
# Tool 2: outlook_list_emails DTOs
# =====================================================================


class ListEmailsRequest(BaseRequest):
    email_type: Annotated[
        EmailTypeOption,
        Field(
            default=EmailTypeOption.ALL,
            description="Filter by sent, received, or all emails",
        ),
    ] = EmailTypeOption.ALL
    sender_receiver: Annotated[
        Optional[str],
        Field(
            default=None, description="Search term for sender or receiver email/name"
        ),
    ] = None
    email_subject: Annotated[
        Optional[str], Field(default=None, description="Search term for the subject")
    ] = None
    body: Annotated[
        Optional[str],
        Field(default=None, description="Search term to find within the email body"),
    ] = None
    is_read: Annotated[
        Optional[bool],
        Field(
            default=None,
            description="Filter by read status (True for read, False for unread, None for both)",
        ),
    ] = None
    min_date: Annotated[
        Optional[str], Field(default=None, description="Minimum date (YYYY-MM-DD)")
    ] = None
    max_date: Annotated[
        Optional[str], Field(default=None, description="Maximum date (YYYY-MM-DD)")
    ] = None
    folder_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Specific folder ID to search in. If None, searches all folders.",
        ),
    ] = None
    sort_by: Annotated[SortByOption, Field(default=SortByOption.DATE)] = (
        SortByOption.DATE
    )
    sort_order: Annotated[
        SortOrderOption, Field(default=SortOrderOption.DESCENDING)
    ] = SortOrderOption.DESCENDING

    # Pagination and Cache
    page: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            description="The page number for fetching paginated results (1-indexed)",
        ),
    ]
    limit: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum number of emails to return per page",
        ),
    ]
    use_cache: Annotated[
        bool,
        Field(default=True, description="Whether to use cached results if available"),
    ] = True

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.min_date and self.max_date and self.min_date > self.max_date:
            raise ValueError("min_date cannot be greater than max_date")
        return self


class ListEmailsResponse(BaseResponse, BasePaginatedResponse):
    objects_found: Annotated[
        list[EmailInformationPreview], Field(description="List of found emails")
    ]
    total_items_matched: Annotated[
        int,
        Field(description="Number of total emails matching the query across all pages"),
    ]


# =====================================================================
# Tool 3: outlook_read_email DTOs
# =====================================================================


class ReadEmailRequest(BaseRequest):
    email_id: Annotated[str, Field(description="The unique ID of the email to read")]


class ReadEmailResponse(BaseResponse):
    email: Annotated[
        EmailInformationFull, Field(description="The complete email details")
    ]


# =====================================================================
# Tool 4: outlook_read_email_attachment DTOs
# =====================================================================


class ReadFileRequest(BaseRequest):
    filename: Annotated[str, Field(description="The name of the file to read")]
    file_id: Annotated[str, Field(description="The attachment ID")]
    email_id: Annotated[
        str, Field(description="The ID of the email containing the attachment")
    ]
    use_cache: Annotated[
        bool,
        Field(default=True, description="Whether to use cached GCS file if available"),
    ] = True


class ReadFileResponse(BaseResponse):
    gcs_uri: Annotated[
        Optional[str],
        Field(default=None, description="The GCS URI where the file was ingested"),
    ] = None
    mime_type: Annotated[
        Optional[str], Field(default=None, description="The MIME type of the file")
    ] = None
    filename: Annotated[
        Optional[str], Field(default=None, description="The name of the file")
    ] = None
    inject_file_data: Annotated[
        bool,
        Field(default=True, description="Flag to trigger multimodal file injection"),
    ] = True


# =====================================================================
# Write, Draft, & Outgoing Operations (Preserved Workflows)
# =====================================================================


class SendMailRequest(BaseRequest):
    to: Annotated[
        list[OutlookRecipient],
        Field(min_length=1, max_length=10, description="Primary recipients."),
    ]
    subject: Annotated[
        str,
        Field(min_length=1, max_length=200, description="Email subject."),
    ]
    body: Annotated[
        str,
        Field(
            min_length=1, max_length=20_000, description="Email body as text or HTML."
        ),
    ]
    cc: Annotated[
        list[OutlookRecipient],
        Field(default_factory=list, max_length=10, description="CC recipients."),
    ]
    save_to_sent_items: Annotated[
        bool,
        Field(
            default=True,
            description="Whether Graph should save the message to Sent Items.",
        ),
    ] = True

    @field_validator("subject")
    @classmethod
    def subject_must_not_be_empty(cls, value: str) -> str:
        return value.strip()


class SendMailResponse(BaseResponse):
    sent: bool = False


class CreateDraftRequest(SendMailRequest):
    pass


class CreateDraftResponse(BaseResponse):
    draft_id: str | None = None
    web_link: str | None = None


class SendDraftRequest(BaseRequest):
    draft_id: Annotated[
        str,
        Field(min_length=1, max_length=300, description="Draft message ID to send."),
    ]


class SendDraftResponse(BaseResponse):
    sent: bool = False
