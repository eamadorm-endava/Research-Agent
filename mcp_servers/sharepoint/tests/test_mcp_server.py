import pytest

from mcp_servers.sharepoint.app import mcp_server
from mcp_servers.sharepoint.app.schemas import (
    SearchSitesRequest,
    SharePointSite,
    IngestDriveItemRequest,
)


class FakeSharePointClient:
    """Simple fake client used to isolate MCP tool wrappers from Microsoft Graph."""

    def search_sites(self, query: str, max_results: int) -> list[SharePointSite]:
        return [
            SharePointSite(
                site_id="site-1",
                name="finance",
                display_name="Finance",
            )
        ]

    def copy_file_to_landing_zone(self, request: IngestDriveItemRequest):
        raise RuntimeError("access_token=secret-token forbidden")


@pytest.mark.asyncio
async def test_search_sharepoint_sites_should_return_success(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "create_sharepoint_client",
        lambda: FakeSharePointClient(),
    )

    response = await mcp_server.search_sharepoint_sites(
        SearchSitesRequest(query="finance", max_results=5)
    )

    assert response.execution_status == "success"
    assert response.sites[0].display_name == "Finance"


@pytest.mark.asyncio
async def test_ingest_sharepoint_drive_item_should_sanitize_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "create_sharepoint_client",
        lambda: FakeSharePointClient(),
    )

    response = await mcp_server.ingest_sharepoint_drive_item(
        IngestDriveItemRequest(drive_id="drive-1", item_id="file-1", filename=None)
    )

    assert response.execution_status == "error"
    assert response.inject_file_data is False
    assert "access_token=[REDACTED]" in response.execution_message
