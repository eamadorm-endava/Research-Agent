from enum import Enum
from typing import Annotated, Optional, Literal
from pydantic import BaseModel, EmailStr, Field, model_validator
from typing_extensions import Self


class ExecutionStatus(str, Enum):
    """Represents the execution status of a task."""

    SUCCESS = "success"
    ERROR = "error"


class AgentDependencies(BaseModel):
    """Injected framework parameters hidden from the LLM."""

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
    """Base request class for all MCP tools."""

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
            Any -> The modified JSON Schema.
        """
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
    """Base response class for all MCP tools."""

    execution_status: Annotated[
        ExecutionStatus,
        Field(description="Whether the operation succeeded or failed."),
    ] = ExecutionStatus.SUCCESS
    error_message: Annotated[
        str | None,
        Field(description="Error message when execution_status is error."),
    ] = None


class BasePaginatedResponse(BaseModel):
    """Base response class for paginated results."""

    current_page: Annotated[
        int, Field(default=1, description="The current page number.")
    ] = 1
    total_pages: Annotated[
        int, Field(default=1, description="Total number of pages available.")
    ] = 1
    has_next: Annotated[
        bool, Field(default=False, description="Whether a next page exists.")
    ] = False


class EmailTypeOption(str, Enum):
    """Enumeration for email type filters."""

    SENT = "sent"
    RECEIVED = "received"
    ALL = "all"


class SortByOption(str, Enum):
    """Enumeration for email sorting options."""

    DATE = "date"
    SUBJECT = "subject"
    SENDER = "sender"


class SortOrderOption(str, Enum):
    """Enumeration for sort directions."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class PersonalData(BaseModel):
    """Represents an individual's contact details."""

    name: Annotated[
        Optional[str], Field(default=None, description="Name of the person")
    ] = None
    email: Annotated[str, Field(description="Email address of the person")]


class OutlookRecipient(BaseModel):
    """Represents a recipient in an Outlook email."""

    email: Annotated[EmailStr, Field(description="Recipient email address.")]
    name: Annotated[
        str | None, Field(default=None, description="Optional recipient display name.")
    ] = None


class AttachmentInfo(BaseModel):
    """Represents basic attachment metadata."""

    file_name: Annotated[str, Field(description="Name of the attached file")]
    mime_type: Annotated[str, Field(description="MIME type of the file")]
    attachment_id: Annotated[str, Field(description="Unique ID of the attachment")]
    size_megabytes: Annotated[
        float, Field(description="Size of the attachment in megabytes")
    ]
    attachment_type: Annotated[
        str,
        Field(
            default="#microsoft.graph.fileAttachment",
            description="The OData type of the attachment (e.g. #microsoft.graph.referenceAttachment or #microsoft.graph.fileAttachment)",
        ),
    ]


class FolderInfo(BaseModel):
    """Represents an Outlook mail folder."""

    folder_id: Annotated[str, Field(description="Unique identifier for the folder")]
    display_name: Annotated[
        str, Field(description="Name of the folder (e.g., 'Inbox', 'Junk Email')")
    ]
    total_item_count: Annotated[
        int, Field(description="Total number of items in the folder")
    ]
    unread_item_count: Annotated[int, Field(description="Number of unread items")]


class EmailInformationPreview(BaseModel):
    """Represents a lightweight email preview for lists."""

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
    """Represents a detailed email object with full metadata."""

    email_body: Annotated[
        Optional[str], Field(default="", description="The complete body of the email")
    ]
    attachments: Annotated[
        list[AttachmentInfo],
        Field(default_factory=list, description="List of all attachments"),
    ]


class DownloadableFiles(str, Enum):
    """Represents the resulting downloaded file from an attachment."""

    PDF = "application/pdf"
    CSV = "text/csv"


class Attendee(BaseModel):
    """
    Data structure representing a calendar event attendee, including their email, name, and organizer status.
    """

    email: Annotated[str, Field(description="Email address of the attendee")]
    name: Annotated[
        Optional[str], Field(default=None, description="Name of the attendee")
    ]
    organizer: Annotated[
        bool,
        Field(
            default=False, description="True if this attendee is the meeting organizer"
        ),
    ]


class CalendarEventPreview(BaseModel):
    """
    Core data structure containing the primary details of a calendar event, suitable for list views.
    """

    event_id: Annotated[
        str, Field(description="Unique identifier for the calendar event")
    ]
    event_name: Annotated[
        Optional[str], Field(default="", description="Subject or name of the event")
    ]
    event_description: Annotated[
        Optional[str],
        Field(default="", description="A short preview of the event body"),
    ]
    start_time: Annotated[
        str, Field(description="Start time of the event in ISO format")
    ]
    duration: Annotated[
        str,
        Field(
            description="Duration of the event (e.g., 'PT1H') or calculated from start/end"
        ),
    ]
    attendees: Annotated[
        list[Attendee], Field(default_factory=list, description="List of participants")
    ]
    join_url: Annotated[
        Optional[str],
        Field(
            default=None,
            description="URL to join the online meeting (e.g. Teams, WebEx)",
        ),
    ]
    has_attachments: Annotated[
        bool, Field(default=False, description="True if the event has attachments")
    ]


class CalendarEventFull(CalendarEventPreview):
    """
    Extended data structure containing the full details of a calendar event, including its body and attachments.
    """

    event_body: Annotated[
        Optional[str], Field(default="", description="The complete body of the event")
    ]
    attachments: Annotated[
        list[AttachmentInfo],
        Field(default_factory=list, description="List of all attachments"),
    ]


DateFilterType = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Date filter in YYYY-MM-DD format.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
]

TimeFilterType = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Time filter in HH:MM:SSZ or HH:MM:SS[+-]HH:MM format.",
        pattern=r"^\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$",
    ),
]


class ListFoldersRequest(BaseRequest):
    """Request schema for listing folders."""

    pass


class ListFoldersResponse(BaseResponse):
    """Response schema for listing folders."""

    folders: Annotated[list[FolderInfo], Field(description="List of mail folders")]


class ListEmailsRequest(BaseRequest):
    """Request schema for listing emails with filters."""

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
    ]
    email_subject: Annotated[
        Optional[str], Field(default=None, description="Search term for the subject")
    ]
    body: Annotated[
        Optional[str],
        Field(default=None, description="Search term to find within the email body"),
    ]
    is_read: Annotated[
        Optional[bool],
        Field(
            default=None,
            description="Filter by read status (True for read, False for unread, None for both)",
        ),
    ]
    min_date: Annotated[
        Optional[str], Field(default=None, description="Minimum date (YYYY-MM-DD)")
    ]
    max_date: Annotated[
        Optional[str], Field(default=None, description="Maximum date (YYYY-MM-DD)")
    ]
    folder_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Specific folder ID to search in. If None, searches all folders.",
        ),
    ]
    sort_by: Annotated[SortByOption, Field(default=SortByOption.DATE)]
    sort_order: Annotated[SortOrderOption, Field(default=SortOrderOption.DESCENDING)]

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
    ]

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """
        Validates that date inputs match the required format.

        Args:
            None

        Returns:
            Self -> The validated object instance.
        """
        if self.min_date and self.max_date and self.min_date > self.max_date:
            raise ValueError("min_date cannot be greater than max_date")
        return self


class ListEmailsResponse(BaseResponse, BasePaginatedResponse):
    """Response schema for listing emails."""

    objects_found: Annotated[
        list[EmailInformationPreview], Field(description="List of found emails")
    ]
    total_items_matched: Annotated[
        int,
        Field(description="Number of total emails matching the query across all pages"),
    ]


class ReadEmailRequest(BaseRequest):
    """Request schema for reading a specific email."""

    email_id: Annotated[str, Field(description="The unique ID of the email to read")]


class ReadEmailResponse(BaseResponse):
    """Response schema for reading a specific email."""

    email: Annotated[
        EmailInformationFull, Field(description="The complete email details")
    ]


class ReadFileRequest(BaseRequest):
    """Request schema for downloading attachments."""

    filename: Annotated[str, Field(description="The name of the file to read")]
    file_id: Annotated[str, Field(description="The attachment ID")]
    email_id: Annotated[
        str, Field(description="The ID of the email containing the attachment")
    ]
    use_cache: Annotated[
        bool,
        Field(default=True, description="Whether to use cached GCS file if available"),
    ]


class ReadFileResponse(BaseResponse):
    """Response schema for downloading attachments."""

    gcs_uri: Annotated[
        Optional[str],
        Field(default=None, description="The GCS URI where the file was ingested"),
    ]
    mime_type: Annotated[
        Optional[str], Field(default=None, description="The MIME type of the file")
    ]
    filename: Annotated[
        Optional[str], Field(default=None, description="The name of the file")
    ]
    inject_file_data: Annotated[
        bool,
        Field(default=True, description="Flag to trigger multimodal file injection"),
    ]


class ListCalendarEventsRequest(BaseRequest):
    """
    Request model for listing calendar events using date, time, and text search filters.
    """

    max_events: Annotated[
        int, Field(default=30, description="The maximum number of events to return.")
    ]
    date_min: DateFilterType
    time_min: TimeFilterType
    date_max: DateFilterType
    time_max: TimeFilterType
    sort_order: Annotated[
        Optional[Literal["asc", "desc"]],
        Field(
            default="asc",
            description="The direction of sorting. 'asc' for ascending, 'desc' for descending (newest first).",
        ),
    ]
    search_term: Annotated[
        Optional[str],
        Field(default=None, description="Free text search terms to find events."),
    ]

    @model_validator(mode="after")
    def validate_time_filters(self) -> Self:
        """
        Validates that time inputs match the required format.

        Args:
            None

        Returns:
            Self -> The validated object instance.
        """
        if (self.time_min or self.time_max) and (
            not self.date_min or not self.date_max
        ):
            raise ValueError(
                "Dates (date_min and date_max) are required when using time filters."
            )
        if bool(self.date_min) != bool(self.date_max):
            raise ValueError(
                "Both date_min and date_max are required for a valid date-time search range."
            )
        return self


class ListCalendarEventsResponse(BaseResponse):
    """
    Response model returning a list of calendar event previews.
    """

    server_current_time_utc: Annotated[
        Optional[str],
        Field(default=None, description="The current server time in UTC format."),
    ]
    events: Annotated[
        list[CalendarEventPreview],
        Field(default_factory=list, description="List of calendar events found."),
    ]


class ReadCalendarEventRequest(BaseRequest):
    """
    Request model for fetching the full details of a specific calendar event.
    """

    event_id: Annotated[str, Field(description="The unique ID of the event to read")]


class ReadCalendarEventResponse(BaseResponse):
    """
    Response model returning the complete details of a calendar event.
    """

    event: Annotated[CalendarEventFull, Field(description="The complete event details")]


class ReadCalendarEventAttachmentRequest(BaseRequest):
    """
    Request model for downloading a specific file attachment from a calendar event.
    """

    filename: Annotated[str, Field(description="The name of the file to read")]
    file_id: Annotated[str, Field(description="The attachment ID")]
    event_id: Annotated[
        str, Field(description="The ID of the event containing the attachment")
    ]
    use_cache: Annotated[
        bool,
        Field(default=True, description="Whether to use cached GCS file if available"),
    ]


class ReadCalendarEventAttachmentResponse(ReadFileResponse):
    """
    Response model returning the GCS URI of the downloaded calendar event attachment.
    """

    pass
