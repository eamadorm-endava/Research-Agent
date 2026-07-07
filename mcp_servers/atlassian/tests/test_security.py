import pytest

from mcp_servers.atlassian.app.atlassian.url_utils import is_atlassian_cloud_url
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


def test_is_atlassian_cloud_url_accepts_valid_cloud_hosts() -> None:
    """Test Atlassian Cloud detection checks the parsed hostname."""
    assert is_atlassian_cloud_url("https://test.atlassian.net")
    assert is_atlassian_cloud_url("https://team.subdomain.atlassian.net/wiki")
    assert is_atlassian_cloud_url("test.atlassian.net")


def test_is_atlassian_cloud_url_rejects_embedded_or_lookalike_hosts() -> None:
    """Test Atlassian Cloud detection rejects raw-string substring bypasses."""
    assert not is_atlassian_cloud_url("https://evil.example.com/test.atlassian.net")
    assert not is_atlassian_cloud_url("https://test.atlassian.net.evil.example.com")
    assert not is_atlassian_cloud_url("https://evil-atlassian.net")
    assert not is_atlassian_cloud_url("https://atlassian.net.evil.example.com")
    assert not is_atlassian_cloud_url("not a url with test.atlassian.net in it")
