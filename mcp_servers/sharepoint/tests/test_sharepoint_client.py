import httpx
import pytest

from mcp_servers.sharepoint.app.schemas import (
    AgentDependencies,
    IngestDriveItemRequest,
    SharePointDriveItem,
    SharePointItemKind,
)
from mcp_servers.sharepoint.app.sharepoint_client import SharePointClient


def _client_with_transport(handler: httpx.MockTransport) -> SharePointClient:
    client = SharePointClient(access_token="token")
    client.http_client = httpx.Client(transport=handler, follow_redirects=True)
    return client


def test_search_sites_should_normalize_graph_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sites")
        assert request.url.params.get("search") == "finance"
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "contoso.sharepoint.com,site-id,web-id",
                        "name": "finance",
                        "displayName": "Finance",
                        "webUrl": "https://contoso.sharepoint.com/sites/finance",
                    }
                ]
            },
        )

    client = _client_with_transport(httpx.MockTransport(handler))
    sites = client.search_sites(query="finance", max_results=5)

    assert len(sites) == 1
    assert sites[0].site_id == "contoso.sharepoint.com,site-id,web-id"
    assert sites[0].display_name == "Finance"


def test_list_drive_items_should_normalize_file_and_folder_items() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/drives/drive-1/root:/Shared%20Documents/Reports:/children" in str(
            request.url
        )
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "file-1",
                        "name": "brief.pdf",
                        "size": 123,
                        "file": {"mimeType": "application/pdf"},
                        "parentReference": {"driveId": "drive-1", "id": "folder-1"},
                    },
                    {
                        "id": "folder-2",
                        "name": "Archive",
                        "folder": {"childCount": 3},
                    },
                ]
            },
        )

    client = _client_with_transport(httpx.MockTransport(handler))
    items = client.list_drive_items(
        drive_id="drive-1",
        item_id=None,
        folder_path="Shared Documents/Reports",
        max_results=10,
    )

    assert [item.kind for item in items] == [
        SharePointItemKind.FILE,
        SharePointItemKind.FOLDER,
    ]
    assert items[0].mime_type == "application/pdf"
    assert items[1].child_count == 3


def test_copy_file_to_landing_zone_should_return_injection_response(
    monkeypatch,
) -> None:
    client = SharePointClient(access_token="token")
    file_item = SharePointDriveItem(
        item_id="file-1",
        name="brief.pdf",
        kind=SharePointItemKind.FILE,
        mime_type="application/pdf",
    )
    streamed: list[str] = []
    granted: list[str] = []

    monkeypatch.setattr(client, "get_drive_item", lambda drive_id, item_id: file_item)
    monkeypatch.setattr(
        client,
        "_stream_graph_file_to_gcs",
        lambda **kwargs: streamed.append(kwargs["destination_object_name"]),
    )
    monkeypatch.setattr(
        client,
        "_grant_landing_zone_read_access",
        lambda folder_prefix, user_email: granted.append(user_email),
    )

    response = client.copy_file_to_landing_zone(
        IngestDriveItemRequest(
            drive_id="drive-1",
            item_id="file-1",
            filename=None,
            dependencies=AgentDependencies(
                app_name="core_agent",
                user_id="user@example.com",
                session_id="session-1",
            ),
        )
    )

    assert response.execution_status == "success"
    assert response.inject_file_data is True
    assert response.gcs_uri is not None
    assert "/session-1/sharepoint-" in response.gcs_uri
    assert streamed[0].endswith("-brief.pdf")
    assert granted == ["user@example.com"]


def test_copy_file_to_landing_zone_should_reject_folders(monkeypatch) -> None:
    client = SharePointClient(access_token="token")
    folder_item = SharePointDriveItem(
        item_id="folder-1",
        name="Archive",
        kind=SharePointItemKind.FOLDER,
    )
    monkeypatch.setattr(client, "get_drive_item", lambda drive_id, item_id: folder_item)

    with pytest.raises(ValueError, match="Only SharePoint files"):
        client.copy_file_to_landing_zone(
            IngestDriveItemRequest(
                drive_id="drive-1",
                item_id="folder-1",
                filename=None,
                dependencies=AgentDependencies(
                    app_name="core_agent",
                    user_id="user@example.com",
                    session_id="session-1",
                ),
            )
        )


def test_list_site_pages_should_normalize_page_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/sites/site-1/pages/microsoft.graph.sitePage" in str(request.url)
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "page-1",
                        "name": "Home.aspx",
                        "title": "Home",
                        "webUrl": "https://contoso.sharepoint.com/sites/finance/SitePages/Home.aspx",
                        "pageLayout": "article",
                    }
                ]
            },
        )

    client = _client_with_transport(httpx.MockTransport(handler))
    pages = client.list_site_pages(site_id="site-1", max_results=5)

    assert len(pages) == 1
    assert pages[0].page_id == "page-1"
    assert pages[0].title == "Home"


def test_get_site_page_should_extract_text_from_canvas_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/sites/site-1/pages/page-1/microsoft.graph.sitePage" in str(request.url)
        assert request.url.params.get("$expand") == "canvasLayout"
        return httpx.Response(
            200,
            json={
                "id": "page-1",
                "name": "Home.aspx",
                "title": "Finance Overview",
                "canvasLayout": {
                    "horizontalSections": [
                        {
                            "columns": [
                                {
                                    "webparts": [
                                        {
                                            "innerHtml": "<p>Q4 finance planning summary</p>",
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
            },
        )

    client = _client_with_transport(httpx.MockTransport(handler))
    page = client.get_site_page(site_id="site-1", page_id="page-1", max_text_chars=2000)

    assert page.title == "Finance Overview"
    assert "Q4 finance planning summary" in page.content_text
    assert page.component_count >= 1


def test_list_list_items_should_return_fields_and_preview() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/sites/site-1/lists/list-1/items" in str(request.url)
        assert request.url.params.get("$expand") == "fields"
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "1",
                        "webUrl": "https://contoso.sharepoint.com/items/1",
                        "fields": {
                            "Title": "Roadmap",
                            "Status": "Approved",
                            "Priority": 1,
                        },
                    }
                ]
            },
        )

    client = _client_with_transport(httpx.MockTransport(handler))
    items = client.list_list_items(site_id="site-1", list_id="list-1", max_results=5)

    assert items[0].fields["Title"] == "Roadmap"
    assert "Status: Approved" in items[0].text_preview
