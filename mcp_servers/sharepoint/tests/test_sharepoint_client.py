import sys
import types
from unittest.mock import patch

import pytest
from pydantic import SecretStr

if "google.cloud.storage" not in sys.modules:
    google_module = sys.modules.setdefault("google", types.ModuleType("google"))
    cloud_module = sys.modules.setdefault(
        "google.cloud", types.ModuleType("google.cloud")
    )
    storage_module = types.ModuleType("google.cloud.storage")
    storage_module.Client = object
    cloud_module.storage = storage_module
    google_module.cloud = cloud_module
    sys.modules["google.cloud.storage"] = storage_module

from mcp_servers.sharepoint.app.schemas import (
    GetSharePointSitePageRequest,
    IngestSharePointDriveItemRequest,
    ListSharePointDriveItemsRequest,
    ListSharePointListItemsRequest,
    SessionContext,
)
from mcp_servers.sharepoint.app.sharepoint_client import SharePointClient


@pytest.fixture
def mock_gcs_connector():
    with patch("mcp_servers.sharepoint.app.sharepoint_client.GCSConnector") as mock:
        yield mock


@pytest.fixture
def base_client(mock_gcs_connector):
    return SharePointClient(SecretStr("mock-token"))


def test_init_requires_token(mock_gcs_connector):
    with pytest.raises(ValueError):
        SharePointClient(SecretStr(""))


def test_format_drive_item_file(base_client):
    raw_item = {
        "id": "file-id",
        "name": "Plan.docx",
        "file": {
            "mimeType": (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        },
        "size": 128,
        "createdBy": {"user": {"displayName": "Ada"}},
        "lastModifiedBy": {"user": {"email": "ada@example.com"}},
    }

    item = base_client._format_drive_item(raw_item)

    assert item.item_id == "file-id"
    assert item.item_type == "file"
    assert (
        item.mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert item.created_by == "Ada"
    assert item.last_modified_by == "ada@example.com"


def test_format_drive_item_folder(base_client):
    raw_item = {
        "id": "folder-id",
        "name": "Project Alpha",
        "folder": {"childCount": 3},
    }

    item = base_client._format_drive_item(raw_item)

    assert item.item_type == "folder"
    assert item.child_count == 3


def test_list_item_preview_uses_visible_fields(base_client):
    raw_item = {
        "id": "1",
        "fields": {
            "Title": "Budget Review",
            "Status": "Published",
            "@odata.etag": "skip-me",
            "Nested": {"skip": True},
        },
    }

    item = base_client._format_list_item(raw_item)

    assert item.fields == {
        "Title": "Budget Review",
        "Status": "Published",
        "Nested": {"skip": True},
    }
    assert item.text_preview == "Title: Budget Review | Status: Published"


def test_extract_page_text_reads_canvas_content(base_client):
    payload = {
        "id": "page-id",
        "title": "Quarterly Update",
        "webUrl": "https://contoso.sharepoint.com/page.aspx",
        "canvasLayout": {
            "horizontalSections": [
                {
                    "columns": [
                        {
                            "webparts": [
                                {
                                    "innerHtml": "<p>Revenue increased by 12%.</p>",
                                    "webPartData": {"description": "Executive summary"},
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    }

    text = base_client._extract_page_text(payload)

    assert "Quarterly Update" in text
    assert "Revenue increased by 12%." in text
    assert "Executive summary" in text
    assert "https://" not in text


@pytest.mark.asyncio
async def test_list_drive_items_uses_request_endpoint(base_client):
    request = ListSharePointDriveItemsRequest(
        drive_id="drive-id",
        parent_item_id="folder-id",
        use_cache=False,
    )

    with patch.object(base_client, "_fetch_collection", return_value=[]) as mock_fetch:
        response = await base_client.list_sharepoint_drive_items(request)

    mock_fetch.assert_called_once_with(
        "/drives/drive-id/items/folder-id/children", False
    )
    assert response.execution_status == "success"
    assert response.total_items == 0


@pytest.mark.asyncio
async def test_list_items_expands_fields(base_client):
    request = ListSharePointListItemsRequest(
        site_id="site-id",
        list_id="list-id",
        use_cache=False,
    )

    with patch.object(base_client, "_fetch_collection", return_value=[]) as mock_fetch:
        await base_client.list_sharepoint_list_items(request)

    mock_fetch.assert_called_once_with(
        "/sites/site-id/lists/list-id/items?expand=fields",
        False,
    )


@pytest.mark.asyncio
async def test_get_page_extracts_text(base_client):
    request = GetSharePointSitePageRequest(site_id="site-id", page_id="page-id")
    payload = {"id": "page-id", "title": "Page", "canvasLayout": {"text": "Body"}}

    with patch.object(base_client, "_get", return_value=payload):
        response = await base_client.get_sharepoint_site_page(request)

    assert response.page.page_id == "page-id"
    assert "Page" in response.text
    assert "Body" in response.text


@pytest.mark.asyncio
async def test_ingest_rejects_folder(base_client):
    dependencies = SessionContext(
        app_name="app",
        user_id="user@example.com",
        session_id="session",
    )
    request = IngestSharePointDriveItemRequest(
        drive_id="drive-id",
        item_id="folder-id",
        dependencies=dependencies,
        use_cache=False,
    )

    with patch.object(
        base_client, "_get", return_value={"id": "folder-id", "folder": {}}
    ):
        with pytest.raises(ValueError) as exc_info:
            await base_client.ingest_sharepoint_drive_item(request)

    assert "Only file drive items can be ingested" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingest_uploads_file(base_client, mock_gcs_connector):
    dependencies = SessionContext(
        app_name="app",
        user_id="user@example.com",
        session_id="session",
    )
    request = IngestSharePointDriveItemRequest(
        drive_id="drive-id",
        item_id="file-id",
        dependencies=dependencies,
        use_cache=False,
    )
    mock_gcs_connector.return_value.upload_stream.return_value = "gs://bucket/file.docx"

    with (
        patch.object(
            base_client,
            "_get",
            return_value={
                "id": "file-id",
                "name": "file.docx",
                "file": {
                    "mimeType": (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                },
                "size": 64,
            },
        ),
        patch.object(
            base_client,
            "_stream_to_landing_zone",
            return_value="gs://bucket/file.docx",
        ) as mock_stream,
    ):
        response = await base_client.ingest_sharepoint_drive_item(request)

    mock_stream.assert_called_once()
    assert response.gcs_uri == "gs://bucket/file.docx"
    assert response.filename == "file.docx"
    assert response.inject_file_data is True
