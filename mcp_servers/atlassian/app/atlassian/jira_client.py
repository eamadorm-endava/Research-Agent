import base64
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
    """Wrapper client for the Atlassian Jira REST API (Cloud v3 and Server/DC v2)."""

    def __init__(self, email: str, token: str, instance_url: str, cloud_id: str):
        self.email = email
        self.token = token
        self.instance_url = instance_url.rstrip("/")
        self.cloud_id = cloud_id

        self.is_cloud = ".atlassian.net" in self.instance_url.lower()
        self.api_prefix = "/rest/api/3" if self.is_cloud else "/rest/api/2"

        if self.is_cloud:
            auth_str = f"{self.email}:{self.token}"
            encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            auth_header = f"Basic {encoded_auth}"
        else:
            auth_header = f"Bearer {self.token}"

        self.headers = {
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        logger.info(f"JiraClient initialized for instance {self.instance_url} (is_cloud={self.is_cloud})")

    async def list_projects(
        self, request: ListJiraProjectsRequest
    ) -> ListJiraProjectsResponse:
        """Fetch all Jira projects."""
        url = f"{self.instance_url}{self.api_prefix}/project"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
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
        url = f"{self.instance_url}{self.api_prefix}/project/{request.project_id_or_key}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
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
        url = f"{self.instance_url}{self.api_prefix}/project/{request.project_id_or_key}/components"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
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
        url = f"{self.instance_url}{self.api_prefix}/projectCategory"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self.headers, timeout=30)
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
        """Search Jira issues using JQL."""
        url = f"{self.instance_url}{self.api_prefix}/search"
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
        url = f"{self.instance_url}{self.api_prefix}/issue/{request.issue_id_or_key}"
        params = {"expand": "names,renderedFields,comments"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url, params=params, headers=self.headers, timeout=30
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
