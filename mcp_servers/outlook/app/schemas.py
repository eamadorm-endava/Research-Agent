from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


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


class BaseResponse(BaseModel):
    execution_status: Annotated[
        ExecutionStatus,
        Field(description="Whether the operation succeeded or failed."),
    ] = ExecutionStatus.SUCCESS
    error_message: Annotated[
        str | None,
        Field(description="Error message when execution_status is error."),
    ] = None


class OutlookRecipient(BaseModel):
    email: Annotated[EmailStr, Field(description="Recipient email address.")]
    name: Annotated[str | None, Field(description="Optional recipient display name.")] = None


class MessageSummary(BaseModel):
    id: Annotated[str, Field(description="Microsoft Graph message ID.")]
    subject: Annotated[str | None, Field(description="Message subject.")]
    sender: Annotated[str | None, Field(description="Sender email address.")]
    received_at: Annotated[datetime | None, Field(description="Received timestamp.")]
    body_preview: Annotated[str | None, Field(description="Short body preview.")]
    has_attachments: Annotated[bool, Field(description="Whether message has attachments.")] = False
    web_link: Annotated[str | None, Field(description="Outlook web link to the message.")] = None


class GetProfileRequest(BaseRequest):
    pass


class GetProfileResponse(BaseResponse):
    display_name: str | None = None
    email: str | None = None
    user_id: str | None = None


class ListMessagesRequest(BaseRequest):
    folder: Annotated[
        str,
        Field(
            default="Inbox",
            description="Mail folder display name. First iteration should usually use Inbox.",
            pattern=r"^[A-Za-z0-9 _\-/]{1,80}$",
        ),
    ] = "Inbox"

    top: Annotated[
        int,
        Field(default=10, ge=1, le=25, description="Maximum messages to return."),
    ] = 10

    unread_only: Annotated[
        bool,
        Field(default=False, description="Whether to return only unread messages."),
    ] = False


class ListMessagesResponse(BaseResponse):
    messages: list[MessageSummary] = Field(default_factory=list)


class SearchMessagesRequest(BaseRequest):
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Search query to match message content, sender, or subject.",
        ),
    ]

    top: Annotated[
        int,
        Field(default=10, ge=1, le=25, description="Maximum messages to return."),
    ] = 10


class SearchMessagesResponse(BaseResponse):
    messages: list[MessageSummary] = Field(default_factory=list)


class GetMessageRequest(BaseRequest):
    message_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=300,
            description="Microsoft Graph message ID.",
        ),
    ]


class AttachmentMetadata(BaseModel):
    id: str | None = None
    name: str | None = None
    content_type: str | None = None
    size: int | None = None


class GetMessageResponse(BaseResponse):
    id: str | None = None
    subject: str | None = None
    sender: str | None = None
    to_recipients: list[str] = Field(default_factory=list)
    cc_recipients: list[str] = Field(default_factory=list)
    received_at: datetime | None = None
    body_content_type: str | None = None
    body: str | None = None
    attachments: list[AttachmentMetadata] = Field(default_factory=list)


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
        Field(min_length=1, max_length=20_000, description="Email body as text or HTML."),
    ]

    cc: Annotated[
        list[OutlookRecipient],
        Field(default_factory=list, max_length=10, description="CC recipients."),
    ]

    save_to_sent_items: Annotated[
        bool,
        Field(default=True, description="Whether Graph should save the message to Sent Items."),
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
