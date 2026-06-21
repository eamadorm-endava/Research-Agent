from loguru import logger
from mcp.server.fastmcp import FastMCP

from .config import ATLASSIAN_SERVER_CONFIG
from .security import create_atlassian_client
from .schemas import (
    SearchJiraIssuesRequest,
    SearchJiraIssuesResponse,
    GetJiraIssueDetailsRequest,
    GetJiraIssueDetailsResponse,
    ListJiraProjectsRequest,
    ListJiraProjectsResponse,
    GetJiraProjectDetailsRequest,
    GetJiraProjectDetailsResponse,
    ListJiraProjectComponentsRequest,
    ListJiraProjectComponentsResponse,
    ListJiraProjectCategoriesRequest,
    ListJiraProjectCategoriesResponse,
    ListConfluenceSpacesRequest,
    ListConfluenceSpacesResponse,
    ListConfluencePagesRequest,
    ListConfluencePagesResponse,
    SearchConfluencePagesRequest,
    SearchConfluencePagesResponse,
    GetConfluencePageDetailsRequest,
    GetConfluencePageDetailsResponse,
    ReadConfluencePageRequest,
    ReadConfluencePageResponse,
    CreateConfluencePageRequest,
    CreateConfluencePageResponse,
    UpdateConfluencePageRequest,
    UpdateConfluencePageResponse,
    ListConfluencePageAttachmentsRequest,
    ListConfluencePageAttachmentsResponse,
    GetConfluenceAttachmentDetailsRequest,
    GetConfluenceAttachmentDetailsResponse,
    ListConfluencePageCommentsRequest,
    ListConfluencePageCommentsResponse,
    CreateConfluencePageCommentRequest,
    CreateConfluencePageCommentResponse,
    ListConfluencePageLabelsRequest,
    ListConfluencePageLabelsResponse,
)

mcp = FastMCP(
    ATLASSIAN_SERVER_CONFIG.server_name,
    stateless_http=ATLASSIAN_SERVER_CONFIG.stateless_http,
    host=ATLASSIAN_SERVER_CONFIG.default_host,
    port=ATLASSIAN_SERVER_CONFIG.default_port,
)


@mcp.tool()
async def search_jira_issues(
    request: SearchJiraIssuesRequest,
) -> SearchJiraIssuesResponse:
    """Search for issues globally across Jira using JQL.

    Args:
        request: SearchJiraIssuesRequest -> JQL search parameters

    Returns:
        SearchJiraIssuesResponse -> A list of matching issues and status
    """
    logger.info(f"Tool call: search_jira_issues(jql='{request.jql}')")
    try:
        client = create_atlassian_client()
        return await client.search_issues(request)
    except Exception as e:
        logger.exception("Error searching Jira issues")
        return SearchJiraIssuesResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            issues=[],
        )


@mcp.tool()
async def get_jira_issue_details(
    request: GetJiraIssueDetailsRequest,
) -> GetJiraIssueDetailsResponse:
    """Retrieve detailed information of a single Jira issue.

    Args:
        request: GetJiraIssueDetailsRequest -> Ticket lookup key

    Returns:
        GetJiraIssueDetailsResponse -> Detailed ticket fields
    """
    logger.info(f"Tool call: get_jira_issue_details(key='{request.issue_id_or_key}')")
    try:
        client = create_atlassian_client()
        return await client.get_issue_details(request)
    except Exception as e:
        logger.exception("Error fetching Jira issue details")
        return GetJiraIssueDetailsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            issue=None,
        )


@mcp.tool()
async def list_jira_projects(
    request: ListJiraProjectsRequest,
) -> ListJiraProjectsResponse:
    """List all projects available in Jira.

    Args:
        request: ListJiraProjectsRequest -> Empty request payload

    Returns:
        ListJiraProjectsResponse -> Catalog of projects
    """
    logger.info("Tool call: list_jira_projects()")
    try:
        client = create_atlassian_client()
        return await client.list_projects(request)
    except Exception as e:
        logger.exception("Error listing Jira projects")
        return ListJiraProjectsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            projects=[],
        )


@mcp.tool()
async def get_jira_project_details(
    request: GetJiraProjectDetailsRequest,
) -> GetJiraProjectDetailsResponse:
    """Retrieve metadata of a single project including category and lead.

    Args:
        request: GetJiraProjectDetailsRequest -> Project lookup key

    Returns:
        GetJiraProjectDetailsResponse -> Detailed project metadata
    """
    logger.info(
        f"Tool call: get_jira_project_details(key='{request.project_id_or_key}')"
    )
    try:
        client = create_atlassian_client()
        return await client.get_project_details(request)
    except Exception as e:
        logger.exception("Error getting project details")
        return GetJiraProjectDetailsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            project=None,
        )


@mcp.tool()
async def list_jira_project_components(
    request: ListJiraProjectComponentsRequest,
) -> ListJiraProjectComponentsResponse:
    """List components/technologies defined in a project.

    Args:
        request: ListJiraProjectComponentsRequest -> Project lookup key

    Returns:
        ListJiraProjectComponentsResponse -> Tech stack component listings
    """
    logger.info(
        f"Tool call: list_jira_project_components(key='{request.project_id_or_key}')"
    )
    try:
        client = create_atlassian_client()
        return await client.list_project_components(request)
    except Exception as e:
        logger.exception("Error listing project components")
        return ListJiraProjectComponentsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            components=[],
        )


@mcp.tool()
async def list_jira_project_categories(
    request: ListJiraProjectCategoriesRequest,
) -> ListJiraProjectCategoriesResponse:
    """List project categories (representing clients/domains).

    Args:
        request: ListJiraProjectCategoriesRequest -> Empty request payload

    Returns:
        ListJiraProjectCategoriesResponse -> Client categorization listings
    """
    logger.info("Tool call: list_jira_project_categories()")
    try:
        client = create_atlassian_client()
        return await client.list_project_categories(request)
    except Exception as e:
        logger.exception("Error listing project categories")
        return ListJiraProjectCategoriesResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            categories=[],
        )


@mcp.tool()
async def list_confluence_spaces(
    request: ListConfluenceSpacesRequest,
) -> ListConfluenceSpacesResponse:
    """List all Confluence spaces available.

    Args:
        request: ListConfluenceSpacesRequest -> Pagination limit and cursor

    Returns:
        ListConfluenceSpacesResponse -> List of spaces and next page cursor
    """
    logger.info("Tool call: list_confluence_spaces()")
    try:
        client = create_atlassian_client()
        return await client.list_spaces(request)
    except Exception as e:
        logger.exception("Error listing Confluence spaces")
        return ListConfluenceSpacesResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            spaces=[],
        )


@mcp.tool()
async def list_confluence_pages(
    request: ListConfluencePagesRequest,
) -> ListConfluencePagesResponse:
    """List Confluence pages, optionally filtered by space ID.

    Args:
        request: ListConfluencePagesRequest -> Filter criteria, limit, and cursor

    Returns:
        ListConfluencePagesResponse -> List of pages and next page cursor
    """
    logger.info(f"Tool call: list_confluence_pages(space_id='{request.space_id}')")
    try:
        client = create_atlassian_client()
        return await client.list_pages(request)
    except Exception as e:
        logger.exception("Error listing Confluence pages")
        return ListConfluencePagesResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            pages=[],
        )


@mcp.tool()
async def search_confluence_pages(
    request: SearchConfluencePagesRequest,
) -> SearchConfluencePagesResponse:
    """Search Confluence pages using CQL (Confluence Query Language).

    Args:
        request: SearchConfluencePagesRequest -> CQL search parameters

    Returns:
        SearchConfluencePagesResponse -> Matching Confluence pages
    """
    logger.info(f"Tool call: search_confluence_pages(cql='{request.cql}')")
    try:
        client = create_atlassian_client()
        return await client.search_confluence_pages(request)
    except Exception as e:
        logger.exception("Error searching Confluence pages")
        return SearchConfluencePagesResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            pages=[],
        )


@mcp.tool()
async def get_confluence_page_details(
    request: GetConfluencePageDetailsRequest,
) -> GetConfluencePageDetailsResponse:
    """Retrieve metadata of a single Confluence page.

    Args:
        request: GetConfluencePageDetailsRequest -> Page ID

    Returns:
        GetConfluencePageDetailsResponse -> Detailed page metadata
    """
    logger.info(f"Tool call: get_confluence_page_details(id='{request.page_id}')")
    try:
        client = create_atlassian_client()
        return await client.get_page_details(request)
    except Exception as e:
        logger.exception("Error getting Confluence page details")
        return GetConfluencePageDetailsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            page=None,
        )


@mcp.tool()
async def read_confluence_page(
    request: ReadConfluencePageRequest,
) -> ReadConfluencePageResponse:
    """Read Confluence page content and stream it to the GCS Landing Zone.

    Args:
        request: ReadConfluencePageRequest -> Page identifier

    Returns:
        ReadConfluencePageResponse -> Landing Zone path and metadata
    """
    logger.info(f"Tool call: read_confluence_page(id='{request.page_id}')")
    try:
        client = create_atlassian_client()
        return await client.read_confluence_page(request)
    except Exception as e:
        logger.exception("Error reading Confluence page")
        return ReadConfluencePageResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            gcs_uri=None,
            mime_type=None,
            filename=None,
            inject_file_data=False,
        )


@mcp.tool()
async def create_confluence_page(
    request: CreateConfluencePageRequest,
) -> CreateConfluencePageResponse:
    """Create a new page in Confluence.

    Args:
        request: CreateConfluencePageRequest -> Creation attributes (title, body HTML, space ID)

    Returns:
        CreateConfluencePageResponse -> Created page metadata
    """
    logger.info(f"Tool call: create_confluence_page(title='{request.title}')")
    try:
        client = create_atlassian_client()
        return await client.create_confluence_page(request)
    except Exception as e:
        logger.exception("Error creating Confluence page")
        return CreateConfluencePageResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            page=None,
        )


@mcp.tool()
async def update_confluence_page(
    request: UpdateConfluencePageRequest,
) -> UpdateConfluencePageResponse:
    """Update an existing Confluence page.

    Args:
        request: UpdateConfluencePageRequest -> Update attributes (page ID, title, version, HTML body)

    Returns:
        UpdateConfluencePageResponse -> Updated page metadata
    """
    logger.info(f"Tool call: update_confluence_page(id='{request.page_id}')")
    try:
        client = create_atlassian_client()
        return await client.update_confluence_page(request)
    except Exception as e:
        logger.exception("Error updating Confluence page")
        return UpdateConfluencePageResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            page=None,
        )


@mcp.tool()
async def list_confluence_page_attachments(
    request: ListConfluencePageAttachmentsRequest,
) -> ListConfluencePageAttachmentsResponse:
    """List attachments associated with a Confluence page.

    Args:
        request: ListConfluencePageAttachmentsRequest -> Page ID, limit, cursor

    Returns:
        ListConfluencePageAttachmentsResponse -> List of attachments and next cursor
    """
    logger.info(f"Tool call: list_confluence_page_attachments(id='{request.page_id}')")
    try:
        client = create_atlassian_client()
        return await client.list_confluence_page_attachments(request)
    except Exception as e:
        logger.exception("Error listing Confluence page attachments")
        return ListConfluencePageAttachmentsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            attachments=[],
        )


@mcp.tool()
async def get_confluence_attachment_details(
    request: GetConfluenceAttachmentDetailsRequest,
) -> GetConfluenceAttachmentDetailsResponse:
    """Retrieve details of a specific Confluence attachment.

    Args:
        request: GetConfluenceAttachmentDetailsRequest -> Attachment ID

    Returns:
        GetConfluenceAttachmentDetailsResponse -> Detailed attachment metadata
    """
    logger.info(
        f"Tool call: get_confluence_attachment_details(id='{request.attachment_id}')"
    )
    try:
        client = create_atlassian_client()
        return await client.get_confluence_attachment_details(request)
    except Exception as e:
        logger.exception("Error getting Confluence attachment details")
        return GetConfluenceAttachmentDetailsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            attachment=None,
        )


@mcp.tool()
async def list_confluence_page_comments(
    request: ListConfluencePageCommentsRequest,
) -> ListConfluencePageCommentsResponse:
    """List comments associated with a specific Confluence page.

    Args:
        request: ListConfluencePageCommentsRequest -> Page ID, limit, cursor

    Returns:
        ListConfluencePageCommentsResponse -> Page comments and next cursor
    """
    logger.info(f"Tool call: list_confluence_page_comments(id='{request.page_id}')")
    try:
        client = create_atlassian_client()
        return await client.list_confluence_page_comments(request)
    except Exception as e:
        logger.exception("Error listing Confluence page comments")
        return ListConfluencePageCommentsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            comments=[],
        )


@mcp.tool()
async def create_confluence_page_comment(
    request: CreateConfluencePageCommentRequest,
) -> CreateConfluencePageCommentResponse:
    """Create a comment on a Confluence page.

    Args:
        request: CreateConfluencePageCommentRequest -> Body HTML, page ID, parent comment ID

    Returns:
        CreateConfluencePageCommentResponse -> Created comment details
    """
    logger.info(
        f"Tool call: create_confluence_page_comment(page_id='{request.page_id}')"
    )
    try:
        client = create_atlassian_client()
        return await client.create_confluence_page_comment(request)
    except Exception as e:
        logger.exception("Error creating Confluence comment")
        return CreateConfluencePageCommentResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            comment=None,
        )


@mcp.tool()
async def list_confluence_page_labels(
    request: ListConfluencePageLabelsRequest,
) -> ListConfluencePageLabelsResponse:
    """List labels/tags associated with a Confluence page.

    Args:
        request: ListConfluencePageLabelsRequest -> Page ID, limit, cursor

    Returns:
        ListConfluencePageLabelsResponse -> List of labels and next cursor
    """
    logger.info(f"Tool call: list_confluence_page_labels(id='{request.page_id}')")
    try:
        client = create_atlassian_client()
        return await client.list_confluence_page_labels(request)
    except Exception as e:
        logger.exception("Error listing Confluence page labels")
        return ListConfluencePageLabelsResponse(
            execution_status="error",
            execution_message=f"Exception: {str(e)}",
            labels=[],
        )
