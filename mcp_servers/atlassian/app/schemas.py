from typing import Annotated, Any, Literal, Optional
from pydantic import BaseModel, Field


class AgentDependencies(BaseModel):
    """Injected runtime context from the calling agent/application."""

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
    """Base request schema for all Atlassian tools to support DI injection."""

    dependencies: Annotated[
        Optional[AgentDependencies],
        Field(
            default=None,
            exclude=True,
            description="Parameters injected by the framework. Excluded to avoid LLM hallucinations.",
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
    """Base response schema for all Atlassian tools providing status echoing."""

    execution_status: Annotated[
        Literal["success", "error"],
        Field(description="Status of execution: 'success' or 'error'."),
    ]
    execution_message: Annotated[
        Optional[str],
        Field(default=None, description="Detailed execution or error message."),
    ]


# --- Jira Issue Schemas ---


class SearchJiraIssuesRequest(BaseRequest):
    """Parameters for searching Jira issues using JQL."""

    jql: Annotated[
        str,
        Field(
            description="The Jira Query Language (JQL) string to search issues (e.g. 'project=PROJ AND component=React')."
        ),
    ]
    max_results: Annotated[
        Optional[int],
        Field(
            default=50,
            ge=1,
            le=100,
            description="Maximum number of issues to return (default: 50, max: 100).",
        ),
    ]
    next_page_token: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Pagination token returned in the previous search response.",
        ),
    ]


class SearchJiraIssuesResponse(BaseResponse):
    """Response returned by Jira JQL search."""

    issues: Annotated[
        list[dict[str, Any]],
        Field(description="List of matching issues with key, status, and metadata."),
    ]
    next_page_token: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Pagination token to fetch the next page of results.",
        ),
    ]


class GetJiraIssueDetailsRequest(BaseRequest):
    """Parameters for fetching a specific issue's details."""

    issue_id_or_key: Annotated[
        str,
        Field(description="The unique ID or key of the Jira issue (e.g., 'PROJ-123')."),
    ]


class GetJiraIssueDetailsResponse(BaseResponse):
    """Response containing detailed issue fields and comments."""

    issue: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="Detailed issue fields including summary, description, and comments.",
        ),
    ]


# --- Jira Project Metadata & Classification Schemas ---


class ListJiraProjectsRequest(BaseRequest):
    """Parameters for listing projects."""

    pass


class ListJiraProjectsResponse(BaseResponse):
    """Response containing the list of available projects."""

    projects: Annotated[
        list[dict[str, Any]],
        Field(description="List of available projects with key, name, and category."),
    ]


class GetJiraProjectDetailsRequest(BaseRequest):
    """Parameters for retrieving details of a single project."""

    project_id_or_key: Annotated[
        str,
        Field(description="The unique ID or key of the Jira project (e.g., 'PROJ')."),
    ]


class GetJiraProjectDetailsResponse(BaseResponse):
    """Response containing detailed project attributes."""

    project: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="Detailed project fields including category and lead.",
        ),
    ]


class ListJiraProjectComponentsRequest(BaseRequest):
    """Parameters for listing components of a project."""

    project_id_or_key: Annotated[
        str,
        Field(description="The unique ID or key of the Jira project (e.g., 'PROJ')."),
    ]


class ListJiraProjectComponentsResponse(BaseResponse):
    """Response containing components representing technologies used."""

    components: Annotated[
        list[dict[str, Any]],
        Field(
            description="List of components (representing technologies, modules) defined in the project."
        ),
    ]


class ListJiraProjectCategoriesRequest(BaseRequest):
    """Parameters for listing all project categories."""

    pass


class ListJiraProjectCategoriesResponse(BaseResponse):
    """Response listing categories representing clients/domains."""

    categories: Annotated[
        list[dict[str, Any]],
        Field(
            description="List of project categories configured in Jira (representing clients/domains)."
        ),
    ]


# --- Confluence Schemas ---


class ListConfluenceSpacesRequest(BaseRequest):
    """Parameters for listing spaces."""

    limit: Annotated[
        Optional[int],
        Field(
            default=25,
            ge=1,
            le=100,
            description="Maximum number of spaces to return (default: 25, max: 100).",
        ),
    ] = 25
    cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor token returned in the previous spaces response for pagination.",
        ),
    ] = None


class ListConfluenceSpacesResponse(BaseResponse):
    """Response containing the list of accessible spaces."""

    spaces: Annotated[
        list[dict[str, Any]],
        Field(description="List of available spaces with key, name, and ID."),
    ]
    next_cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor to fetch the next page of spaces.",
        ),
    ] = None


class ListConfluencePagesRequest(BaseRequest):
    """Parameters for listing pages."""

    space_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional space ID to filter pages by space.",
        ),
    ] = None
    limit: Annotated[
        Optional[int],
        Field(
            default=25,
            ge=1,
            le=100,
            description="Maximum number of pages to return (default: 25, max: 100).",
        ),
    ] = 25
    cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor token returned in the previous pages response for pagination.",
        ),
    ] = None


class ListConfluencePagesResponse(BaseResponse):
    """Response containing the list of pages."""

    pages: Annotated[
        list[dict[str, Any]],
        Field(description="List of available pages with title, ID, and spaceId."),
    ]
    next_cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor to fetch the next page of pages.",
        ),
    ] = None


class SearchConfluencePagesRequest(BaseRequest):
    """Parameters for searching Confluence pages using CQL."""

    cql: Annotated[
        str,
        Field(
            description="The Confluence Query Language (CQL) string to search pages (e.g., 'title ~ \"Design\"')."
        ),
    ]
    limit: Annotated[
        Optional[int],
        Field(
            default=25,
            ge=1,
            le=100,
            description="Maximum number of pages to return (default: 25, max: 100).",
        ),
    ] = 25
    next_page_token: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Token returned in the previous search response for pagination.",
        ),
    ] = None


class SearchConfluencePagesResponse(BaseResponse):
    """Response containing the matching Confluence pages."""

    pages: Annotated[
        list[dict[str, Any]],
        Field(description="List of matching pages with ID, title, and metadata."),
    ]
    next_page_token: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Token to fetch the next page of search results.",
        ),
    ] = None


class GetConfluencePageDetailsRequest(BaseRequest):
    """Parameters for retrieving details of a single page."""

    page_id: Annotated[
        str,
        Field(description="The unique ID of the Confluence page."),
    ]


class GetConfluencePageDetailsResponse(BaseResponse):
    """Response containing detailed page attributes."""

    page: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="Detailed page fields including space key, title, and status.",
        ),
    ] = None


class ReadConfluencePageRequest(BaseRequest):
    """Parameters to read and ingest a Confluence page into the GCS Landing Zone."""

    page_id: Annotated[
        str,
        Field(description="The unique ID of the Confluence page to ingest."),
    ]


class ReadConfluencePageResponse(BaseResponse):
    """Response pointing to the Landing Zone GCS URI and MIME type."""

    gcs_uri: Annotated[
        Optional[str],
        Field(
            default=None,
            description="The canonical GCS URI of the ingested page document.",
        ),
    ] = None
    mime_type: Annotated[
        Optional[str],
        Field(
            default=None,
            description="The MIME type of the ingested document (typically text/markdown).",
        ),
    ] = None
    filename: Annotated[
        Optional[str],
        Field(default=None, description="Original filename under which it is saved."),
    ] = None
    inject_file_data: Annotated[
        bool,
        Field(
            default=False,
            description="Flag instructing the plugin to load file content natively.",
        ),
    ] = False


class CreateConfluencePageRequest(BaseRequest):
    """Parameters for creating a new Confluence page."""

    space_id: Annotated[
        str,
        Field(description="The unique ID of the space to create the page in."),
    ]
    title: Annotated[
        str,
        Field(description="The title of the new Confluence page."),
    ]
    body_html: Annotated[
        str,
        Field(
            description="The HTML/Storage format content of the page (e.g., '<p>Hello World</p>')."
        ),
    ]
    parent_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional parent page ID to create the page as a child.",
        ),
    ] = None


class CreateConfluencePageResponse(BaseResponse):
    """Response containing the created page details."""

    page: Annotated[
        Optional[dict[str, Any]],
        Field(default=None, description="Metadata of the newly created page."),
    ] = None


class UpdateConfluencePageRequest(BaseRequest):
    """Parameters for updating an existing Confluence page."""

    page_id: Annotated[
        str,
        Field(description="The unique ID of the Confluence page to update."),
    ]
    version_number: Annotated[
        int,
        Field(
            description="The new version number of the page (must be incremented by 1 from current)."
        ),
    ]
    title: Annotated[
        str,
        Field(description="The title of the Confluence page."),
    ]
    body_html: Annotated[
        str,
        Field(
            description="The HTML/Storage format content of the page (e.g., '<p>Updated Content</p>')."
        ),
    ]


class UpdateConfluencePageResponse(BaseResponse):
    """Response containing the updated page details."""

    page: Annotated[
        Optional[dict[str, Any]],
        Field(default=None, description="Metadata of the updated page."),
    ] = None


class ListConfluencePageAttachmentsRequest(BaseRequest):
    """Parameters for listing page attachments."""

    page_id: Annotated[
        str,
        Field(description="The unique ID of the page to list attachments for."),
    ]
    limit: Annotated[
        Optional[int],
        Field(
            default=25,
            ge=1,
            le=100,
            description="Maximum number of attachments to return (default: 25, max: 100).",
        ),
    ] = 25
    cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor token returned in the previous response for pagination.",
        ),
    ] = None


class ListConfluencePageAttachmentsResponse(BaseResponse):
    """Response containing the list of page attachments."""

    attachments: Annotated[
        list[dict[str, Any]],
        Field(description="List of attachments associated with the page."),
    ]
    next_cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor to fetch the next page of attachments.",
        ),
    ] = None


class GetConfluenceAttachmentDetailsRequest(BaseRequest):
    """Parameters for retrieving details of a specific attachment."""

    attachment_id: Annotated[
        str,
        Field(description="The unique ID of the attachment."),
    ]


class GetConfluenceAttachmentDetailsResponse(BaseResponse):
    """Response containing detailed attachment attributes."""

    attachment: Annotated[
        Optional[dict[str, Any]],
        Field(default=None, description="Detailed attachment metadata."),
    ] = None


class ListConfluencePageCommentsRequest(BaseRequest):
    """Parameters for listing page comments."""

    page_id: Annotated[
        str,
        Field(description="The unique ID of the page to list comments for."),
    ]
    limit: Annotated[
        Optional[int],
        Field(
            default=25,
            ge=1,
            le=100,
            description="Maximum number of comments to return (default: 25, max: 100).",
        ),
    ] = 25
    cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor token returned in the previous response for pagination.",
        ),
    ] = None


class ListConfluencePageCommentsResponse(BaseResponse):
    """Response containing page footer comments."""

    comments: Annotated[
        list[dict[str, Any]],
        Field(description="List of comments associated with the page."),
    ]
    next_cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor to fetch the next page of comments.",
        ),
    ] = None


class CreateConfluencePageCommentRequest(BaseRequest):
    """Parameters for creating a comment on a page."""

    page_id: Annotated[
        str,
        Field(description="The unique ID of the page to comment on."),
    ]
    body_html: Annotated[
        str,
        Field(
            description="The HTML/Storage format content of the comment (e.g., '<p>Nice page!</p>')."
        ),
    ]
    parent_comment_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional parent comment ID to reply to an existing comment.",
        ),
    ] = None


class CreateConfluencePageCommentResponse(BaseResponse):
    """Response containing the created comment details."""

    comment: Annotated[
        Optional[dict[str, Any]],
        Field(default=None, description="Metadata of the newly created comment."),
    ] = None


class ListConfluencePageLabelsRequest(BaseRequest):
    """Parameters for listing page labels."""

    page_id: Annotated[
        str,
        Field(description="The unique ID of the page to list labels for."),
    ]
    limit: Annotated[
        Optional[int],
        Field(
            default=25,
            ge=1,
            le=100,
            description="Maximum number of labels to return (default: 25, max: 100).",
        ),
    ] = 25
    cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor token returned in the previous response for pagination.",
        ),
    ] = None


class ListConfluencePageLabelsResponse(BaseResponse):
    """Response containing page labels/tags."""

    labels: Annotated[
        list[dict[str, Any]],
        Field(description="List of labels associated with the page."),
    ]
    next_cursor: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Cursor to fetch the next page of labels.",
        ),
    ] = None
