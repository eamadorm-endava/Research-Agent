import pytest

from mcp_servers.atlassian.app.security import select_accessible_resource


def test_select_accessible_resource_prefers_configured_cloud_id() -> None:
    """Test configured Cloud ID determines which Atlassian site is selected."""
    resources = [
        {"id": "cloud-1", "url": "https://one.atlassian.net", "scopes": []},
        {"id": "cloud-2", "url": "https://two.atlassian.net", "scopes": []},
    ]

    selected = select_accessible_resource(resources, configured_cloud_id="cloud-2")

    assert selected["id"] == "cloud-2"


def test_select_accessible_resource_fails_when_configured_cloud_id_is_missing() -> None:
    """Test inaccessible configured Cloud ID fails fast."""
    resources = [{"id": "cloud-1", "url": "https://one.atlassian.net"}]

    with pytest.raises(RuntimeError, match="not accessible"):
        select_accessible_resource(resources, configured_cloud_id="cloud-2")


def test_select_accessible_resource_prefers_jira_or_confluence_scopes() -> None:
    """Test resource selection prefers Jira/Confluence scoped sites."""
    resources = [
        {"id": "cloud-1", "url": "https://one.atlassian.net", "scopes": []},
        {
            "id": "cloud-2",
            "url": "https://two.atlassian.net",
            "scopes": ["read:jira-work"],
        },
    ]

    selected = select_accessible_resource(resources)

    assert selected["id"] == "cloud-2"
