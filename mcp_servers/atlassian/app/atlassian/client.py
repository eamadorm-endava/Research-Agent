from .jira_client import JiraClient
from .confluence_client import ConfluenceClient
from ..schemas import (
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


class AtlassianClient:
    """Orchestrator client for the Atlassian Jira and Confluence REST APIs."""

    def __init__(self, email: str, token: str, instance_url: str, cloud_id: str):
        self.jira = JiraClient(email, token, instance_url, cloud_id)
        self.confluence = ConfluenceClient(email, token, instance_url, cloud_id)

    # --- Jira Delegations ---

    async def list_projects(
        self, request: ListJiraProjectsRequest
    ) -> ListJiraProjectsResponse:
        return await self.jira.list_projects(request)

    async def get_project_details(
        self, request: GetJiraProjectDetailsRequest
    ) -> GetJiraProjectDetailsResponse:
        return await self.jira.get_project_details(request)

    async def list_project_components(
        self, request: ListJiraProjectComponentsRequest
    ) -> ListJiraProjectComponentsResponse:
        return await self.jira.list_project_components(request)

    async def list_project_categories(
        self, request: ListJiraProjectCategoriesRequest
    ) -> ListJiraProjectCategoriesResponse:
        return await self.jira.list_project_categories(request)

    async def search_issues(
        self, request: SearchJiraIssuesRequest
    ) -> SearchJiraIssuesResponse:
        return await self.jira.search_issues(request)

    async def get_issue_details(
        self, request: GetJiraIssueDetailsRequest
    ) -> GetJiraIssueDetailsResponse:
        return await self.jira.get_issue_details(request)

    # --- Confluence Delegations ---

    async def list_spaces(
        self, request: ListConfluenceSpacesRequest
    ) -> ListConfluenceSpacesResponse:
        return await self.confluence.list_spaces(request)

    async def list_pages(
        self, request: ListConfluencePagesRequest
    ) -> ListConfluencePagesResponse:
        return await self.confluence.list_pages(request)

    async def search_confluence_pages(
        self, request: SearchConfluencePagesRequest
    ) -> SearchConfluencePagesResponse:
        return await self.confluence.search_pages(request)

    async def get_page_details(
        self, request: GetConfluencePageDetailsRequest
    ) -> GetConfluencePageDetailsResponse:
        return await self.confluence.get_page_details(request)

    async def read_confluence_page(
        self, request: ReadConfluencePageRequest
    ) -> ReadConfluencePageResponse:
        return await self.confluence.read_page(request)

    async def create_confluence_page(
        self, request: CreateConfluencePageRequest
    ) -> CreateConfluencePageResponse:
        return await self.confluence.create_page(request)

    async def update_confluence_page(
        self, request: UpdateConfluencePageRequest
    ) -> UpdateConfluencePageResponse:
        return await self.confluence.update_page(request)

    async def list_confluence_page_attachments(
        self, request: ListConfluencePageAttachmentsRequest
    ) -> ListConfluencePageAttachmentsResponse:
        return await self.confluence.list_page_attachments(request)

    async def get_confluence_attachment_details(
        self, request: GetConfluenceAttachmentDetailsRequest
    ) -> GetConfluenceAttachmentDetailsResponse:
        return await self.confluence.get_attachment_details(request)

    async def list_confluence_page_comments(
        self, request: ListConfluencePageCommentsRequest
    ) -> ListConfluencePageCommentsResponse:
        return await self.confluence.list_page_comments(request)

    async def create_confluence_page_comment(
        self, request: CreateConfluencePageCommentRequest
    ) -> CreateConfluencePageCommentResponse:
        return await self.confluence.create_comment(request)

    async def list_confluence_page_labels(
        self, request: ListConfluencePageLabelsRequest
    ) -> ListConfluencePageLabelsResponse:
        return await self.confluence.list_page_labels(request)
