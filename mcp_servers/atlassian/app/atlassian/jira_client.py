from typing import Any
import httpx
from loguru import logger

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
)


class JiraClient:
    """OAuth-only wrapper client for the Atlassian Jira Cloud REST API v3."""

    def __init__(self, access_token: str, instance_url: str, cloud_id: str):
        self.access_token = access_token
        self.instance_url = instance_url.rstrip("/")
        self.cloud_id = cloud_id
        self.is_cloud = True
        self.base_url = self._build_base_url()

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        logger.info(
            f"JiraClient initialized for instance {self.instance_url} "
            "using Atlassian OAuth"
        )

    def _build_base_url(self) -> str:
        """
        Builds the Jira Cloud API gateway base URL for OAuth calls.

        Returns:
            str -> API base URL without a trailing slash.
        """
        if not self.cloud_id:
            raise ValueError("cloud_id is required for Atlassian OAuth mode")
        return f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3"

    async def list_projects(
        self, request: ListJiraProjectsRequest
    ) -> ListJiraProjectsResponse:
        """Fetch all Jira projects."""
        url = f"{self.base_url}/project"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
                if resp.status_code == 404:
                    logger.warning(f"List projects returned 404: {resp.text}")
                    return ListJiraProjectsResponse(
                        execution_status="success",
                        execution_message="No projects found or the endpoint is unavailable.",
                        projects=[],
                    )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list projects: {resp.status_code} {resp.text}"
                    )
                    return ListJiraProjectsResponse(
                        execution_status="error",
                        execution_message=f"Jira API error: {resp.status_code} {resp.text}",
                        projects=[],
                    )
                projects = resp.json()
                return ListJiraProjectsResponse(
                    execution_status="success",
                    projects=projects,
                )
        except Exception as e:
            logger.exception("Exception in list_projects")
            return ListJiraProjectsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                projects=[],
            )

    async def get_project_details(
        self, request: GetJiraProjectDetailsRequest
    ) -> GetJiraProjectDetailsResponse:
        """Fetch detailed information of a single Jira project."""
        url = f"{self.base_url}/project/{request.project_id_or_key}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
                if resp.status_code == 404:
                    logger.warning(f"Project not found: {resp.text}")
                    return GetJiraProjectDetailsResponse(
                        execution_status="success",
                        execution_message=f"Project '{request.project_id_or_key}' was not found. Verify the project key or ID.",
                        project=None,
                    )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to get project details: {resp.status_code} {resp.text}"
                    )
                    return GetJiraProjectDetailsResponse(
                        execution_status="error",
                        execution_message=f"Jira API error: {resp.status_code} {resp.text}",
                        project=None,
                    )
                project = resp.json()
                return GetJiraProjectDetailsResponse(
                    execution_status="success",
                    project=project,
                )
        except Exception as e:
            logger.exception("Exception in get_project_details")
            return GetJiraProjectDetailsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                project=None,
            )

    async def list_project_components(
        self, request: ListJiraProjectComponentsRequest
    ) -> ListJiraProjectComponentsResponse:
        """Fetch all components (representing technologies) for a project."""
        url = f"{self.base_url}/project/{request.project_id_or_key}/components"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
                if resp.status_code == 404:
                    logger.warning(f"Project components not found: {resp.text}")
                    return ListJiraProjectComponentsResponse(
                        execution_status="success",
                        execution_message=f"No components found for project '{request.project_id_or_key}'. Verify the project key or ID.",
                        components=[],
                    )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list components: {resp.status_code} {resp.text}"
                    )
                    return ListJiraProjectComponentsResponse(
                        execution_status="error",
                        execution_message=f"Jira API error: {resp.status_code} {resp.text}",
                        components=[],
                    )
                components = resp.json()
                return ListJiraProjectComponentsResponse(
                    execution_status="success",
                    components=components,
                )
        except Exception as e:
            logger.exception("Exception in list_project_components")
            return ListJiraProjectComponentsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                components=[],
            )

    async def list_project_categories(
        self, request: ListJiraProjectCategoriesRequest
    ) -> ListJiraProjectCategoriesResponse:
        """Fetch all project categories (representing clients/domains)."""
        url = f"{self.base_url}/projectCategory"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
                if resp.status_code == 404:
                    logger.warning(f"Project categories not found: {resp.text}")
                    return ListJiraProjectCategoriesResponse(
                        execution_status="success",
                        execution_message="No project categories found or the endpoint is unavailable.",
                        categories=[],
                    )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to list categories: {resp.status_code} {resp.text}"
                    )
                    return ListJiraProjectCategoriesResponse(
                        execution_status="error",
                        execution_message=f"Jira API error: {resp.status_code} {resp.text}",
                        categories=[],
                    )
                categories = resp.json()
                return ListJiraProjectCategoriesResponse(
                    execution_status="success",
                    categories=categories,
                )
        except Exception as e:
            logger.exception("Exception in list_project_categories")
            return ListJiraProjectCategoriesResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                categories=[],
            )

    async def search_issues(
        self, request: SearchJiraIssuesRequest
    ) -> SearchJiraIssuesResponse:
        """Search Jira issues using JQL.

        Uses the enhanced /search/jql endpoint for Cloud instances (the legacy
        /search was removed by Atlassian on 2025-08-01) and falls back to the
        classic /search endpoint for Server/DC.

        Args:
            request: SearchJiraIssuesRequest -> JQL search parameters

        Returns:
            SearchJiraIssuesResponse -> Matching issues and pagination token
        """
        if self.is_cloud:
            url = f"{self.base_url}/search/jql"
        else:
            url = f"{self.base_url}/search"

        params: dict[str, Any] = {
            "jql": request.jql,
            "maxResults": request.max_results or 50,
            "fields": "key,summary,status,project,priority,assignee,updated",
        }
        if request.next_page_token:
            if self.is_cloud:
                params["nextPageToken"] = request.next_page_token
            else:
                params["startAt"] = int(request.next_page_token)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code == 404:
                    logger.warning(
                        f"Search returned 404 (no matching resource): {resp.text}"
                    )
                    return SearchJiraIssuesResponse(
                        execution_status="success",
                        execution_message=(
                            "The search query returned no results or the "
                            "requested resource was not found. Try broadening "
                            "your JQL query or verifying project/issue keys."
                        ),
                        issues=[],
                    )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to search issues: {resp.status_code} {resp.text}"
                    )
                    return SearchJiraIssuesResponse(
                        execution_status="error",
                        execution_message=f"Jira API error: {resp.status_code} {resp.text}",
                        issues=[],
                    )
                data = resp.json()
                issues = data.get("issues", [])

                next_page_token = None
                if not self.is_cloud:
                    start_at = data.get("startAt", 0)
                    max_results = data.get("maxResults", 50)
                    total = data.get("total", 0)
                    if start_at + max_results < total:
                        next_page_token = str(start_at + max_results)
                else:
                    next_page_token = data.get("nextPageToken")

                return SearchJiraIssuesResponse(
                    execution_status="success",
                    issues=issues,
                    next_page_token=next_page_token,
                )
        except Exception as e:
            logger.exception("Exception in search_issues")
            return SearchJiraIssuesResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                issues=[],
            )

    async def get_issue_details(
        self, request: GetJiraIssueDetailsRequest
    ) -> GetJiraIssueDetailsResponse:
        """Fetch detailed information for a single Jira issue."""
        url = f"{self.base_url}/issue/{request.issue_id_or_key}"
        params = {"expand": "names,renderedFields,comments"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
                )
                if resp.status_code == 404:
                    logger.warning(f"Issue not found: {resp.text}")
                    return GetJiraIssueDetailsResponse(
                        execution_status="success",
                        execution_message=f"Issue '{request.issue_id_or_key}' was not found. Verify the issue key or ID.",
                        issue=None,
                    )
                if resp.status_code != 200:
                    logger.error(
                        f"Failed to get issue details: {resp.status_code} {resp.text}"
                    )
                    return GetJiraIssueDetailsResponse(
                        execution_status="error",
                        execution_message=f"Jira API error: {resp.status_code} {resp.text}",
                        issue=None,
                    )
                issue = resp.json()
                return GetJiraIssueDetailsResponse(
                    execution_status="success",
                    issue=issue,
                )
        except Exception as e:
            logger.exception("Exception in get_issue_details")
            return GetJiraIssueDetailsResponse(
                execution_status="error",
                execution_message=f"Connection failure: {str(e)}",
                issue=None,
            )
