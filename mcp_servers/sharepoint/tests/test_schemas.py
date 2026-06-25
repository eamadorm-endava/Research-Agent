import pytest
from pydantic import ValidationError

from mcp_servers.sharepoint.app.schemas import (
    IngestSharePointDriveItemRequest,
    ListSharePointDriveItemsRequest,
    SearchSharePointDriveItemsRequest,
    SearchSharePointSitesRequest,
)


def test_search_sites_query_cleansing_and_endpoint():
    request = SearchSharePointSitesRequest(query="Alpha ' Portal")

    assert request.query == "Alpha   Portal"
    assert request.endpoint == "/sites?search=Alpha%20%20%20Portal"


def test_drive_item_listing_defaults_to_root_children():
    request = ListSharePointDriveItemsRequest(drive_id="drive-id")

    assert request.endpoint == "/drives/drive-id/root/children"


def test_drive_item_listing_uses_parent_item_id():
    request = ListSharePointDriveItemsRequest(
        drive_id="drive-id",
        parent_item_id="folder-id",
    )

    assert request.endpoint == "/drives/drive-id/items/folder-id/children"


def test_drive_item_listing_uses_root_relative_path():
    request = ListSharePointDriveItemsRequest(
        drive_id="drive-id",
        root_relative_path="Shared Documents/Project Alpha",
    )

    assert (
        request.endpoint
        == "/drives/drive-id/root:/Shared%20Documents/Project%20Alpha:/children"
    )


def test_drive_item_listing_rejects_ambiguous_location():
    with pytest.raises(ValidationError) as exc_info:
        ListSharePointDriveItemsRequest(
            drive_id="drive-id",
            parent_item_id="folder-id",
            root_relative_path="Project Alpha",
        )

    assert "Provide either parent_item_id or root_relative_path" in str(exc_info.value)


def test_search_drive_items_cleanses_query():
    request = SearchSharePointDriveItemsRequest(
        drive_id="drive-id",
        query="project/alpha'notes",
    )

    assert request.query == "project alpha notes"
    assert (
        request.endpoint == "/drives/drive-id/root/search(q='project%20alpha%20notes')"
    )


def test_ingest_request_builds_metadata_and_content_endpoints():
    request = IngestSharePointDriveItemRequest(drive_id="drive-id", item_id="file-id")

    assert request.metadata_endpoint == "/drives/drive-id/items/file-id"
    assert request.content_endpoint == "/drives/drive-id/items/file-id/content"
