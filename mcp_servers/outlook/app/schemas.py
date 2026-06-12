from typing import Optional, Annotated, List, Any
from pydantic import BaseModel, Field

class AgentDependencies(BaseModel):
    app_name: Annotated[str, Field(description="The name of the calling application or agent.")]
    user_id: Annotated[str, Field(description="The unique identifier of the user using the agent")]
    session_id: Annotated[str, Field(description="The current session or conversation ID with the agent")]

class BaseRequest(BaseModel):
    dependencies: Annotated[
        Optional[AgentDependencies],
        Field(
            default=None,
            exclude=True,
            description="Parameters that needs to be injected by the framework. The LLM will not see this to avoid hallucinations.",
        ),
    ]

# --- Tool Schemas --- #

class SearchEmailsRequest(BaseRequest):
    query: Annotated[str, Field(description="The keyword or query string to search for emails (KQL).")]
    top: Annotated[int, Field(default=10, description="The maximum number of emails to retrieve.")]

class SearchEmailsResponse(BaseModel):
    execution_status: str
    emails: List[dict]

class GetEmailRequest(BaseRequest):
    message_id: Annotated[str, Field(description="The unique Graph API message ID of the email to retrieve.")]

class GetEmailResponse(BaseModel):
    execution_status: str
    email_data: Optional[dict]

class SendEmailRequest(BaseRequest):
    to_email: Annotated[str, Field(description="The recipient email address.")]
    subject: Annotated[str, Field(description="The subject of the email.")]
    body: Annotated[str, Field(description="The content of the email.")]

class SendEmailResponse(BaseModel):
    execution_status: str
