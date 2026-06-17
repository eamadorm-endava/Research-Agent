import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from mcp_servers.atlassian.app.atlassian.client import AtlassianClient
from mcp_servers.atlassian.app.schemas import (
    ListJiraProjectsRequest,
    SearchJiraIssuesRequest,
)


@pytest.mark.asyncio
async def test_list_projects_success() -> None:
    """Test successful project list query."""
    client = AtlassianClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"key": "PROJ", "name": "Project Name"}]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = ListJiraProjectsRequest()
        res = await client.list_projects(req)

        assert res.execution_status == "success"
        assert len(res.projects) == 1
        assert res.projects[0]["key"] == "PROJ"
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_list_projects_failure() -> None:
    """Test project list API failure handling."""
    client = AtlassianClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = ListJiraProjectsRequest()
        res = await client.list_projects(req)

        assert res.execution_status == "error"
        assert "Jira API error" in res.execution_message
        assert res.projects == []


@pytest.mark.asyncio
async def test_search_issues_success() -> None:
    """Test successful JQL issue search."""
    client = AtlassianClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "issues": [{"key": "PROJ-1", "fields": {"summary": "Issue 1"}}],
        "nextPageToken": "token-xyz",
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = SearchJiraIssuesRequest(jql="project = PROJ")
        res = await client.search_issues(req)

        assert res.execution_status == "success"
        assert len(res.issues) == 1
        assert res.issues[0]["key"] == "PROJ-1"
        assert res.next_page_token == "token-xyz"
        mock_get.assert_called_once()
        # Ensure fields parameter is passed in params
        args, kwargs = mock_get.call_args
        assert (
            kwargs["params"]["fields"]
            == "key,summary,status,project,priority,assignee,updated"
        )


@pytest.mark.asyncio
async def test_search_issues_failure() -> None:
    """Test JQL issue search API failure handling."""
    client = AtlassianClient(
        email="test@example.com",
        token="token123",
        instance_url="https://test.atlassian.net",
        cloud_id="cloud-123",
    )

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        req = SearchJiraIssuesRequest(jql="project = PROJ")
        res = await client.search_issues(req)

        assert res.execution_status == "error"
        assert "Jira API error" in res.execution_message
        assert res.issues == []
