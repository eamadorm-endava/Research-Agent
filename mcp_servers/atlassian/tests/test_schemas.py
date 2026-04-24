import pytest
from pydantic import ValidationError

from mcp_servers.atlassian.app.schemas import (
    BaseResponse,
    SearchJiraIssuesRequest,
    SearchJiraIssuesResponse,
    GetJiraIssueDetailsResponse,
    ListJiraProjectsResponse,
)


def test_responses_inherit_from_base_response() -> None:
    """Ensure all response models inherit from BaseResponse."""
    assert issubclass(SearchJiraIssuesResponse, BaseResponse)
    assert issubclass(GetJiraIssueDetailsResponse, BaseResponse)
    assert issubclass(ListJiraProjectsResponse, BaseResponse)


def test_base_response_validation() -> None:
    """Test that BaseResponse validates execution_status correctly."""
    with pytest.raises(ValidationError, match="Input should be 'success' or 'error'"):
        _ = BaseResponse(execution_status="pending")  # type: ignore

    resp = BaseResponse(execution_status="success")
    assert resp.execution_status == "success"
    assert resp.execution_message is None


def test_search_jira_issues_request_defaults() -> None:
    """Test that SearchJiraIssuesRequest has correct default parameter values."""
    req = SearchJiraIssuesRequest(jql="project = TEST")
    assert req.max_results == 50
    assert req.next_page_token is None


def test_search_jira_issues_request_validation() -> None:
    """Test that SearchJiraIssuesRequest enforces required query parameters."""
    with pytest.raises(ValidationError, match="Field required"):
        _ = SearchJiraIssuesRequest()  # type: ignore
