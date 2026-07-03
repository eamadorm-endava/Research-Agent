from unittest.mock import MagicMock, patch
import pytest
from mcp_servers.onedrive.app.onedrive_client import OneDriveClient
from mcp_servers.onedrive.app.schemas import (
    ListFolderContentsRequest,
    ReadFileRequest,
    SessionContext,
    FindItemsRequest,
    ObjectTypeOption,
    MainFolder,
)


@pytest.fixture
def mock_access_token():
    mock_token = MagicMock()
    mock_token.get_secret_value.return_value = "mock_token_value"
    return mock_token


@pytest.fixture
def mock_gcs_connector():
    with patch("mcp_servers.onedrive.app.onedrive_client.GCSConnector") as mock:
        yield mock


@pytest.fixture
def base_client(mock_access_token, mock_gcs_connector):
    return OneDriveClient(mock_access_token)


def test_init_no_token():
    with pytest.raises(ValueError):
        OneDriveClient("")


@pytest.mark.asyncio
async def test_list_folder_contents_smart_id(base_client):
    """
    Tests that if a SmartID (driveId|itemId) is passed to list_folder_contents,
    it correctly parses the ID and constructs the appropriate endpoint.
    """
    request = ListFolderContentsRequest(
        folder_id="driveXYZ123|folderABC456",
        page=1,
        use_cache=False,
        sort_by="object_name",
        sort_order="asc",
    )

    with patch.object(base_client, "_fetch_all_items") as mock_fetch:
        mock_fetch.return_value = []

        response = await base_client.list_folder_contents(request)

        mock_fetch.assert_called_once()
        endpoints = mock_fetch.call_args[0][0]
        assert len(endpoints) == 1
        # Check that it constructed the correct SmartID endpoint
        assert endpoints[0] == "/drives/driveXYZ123/items/folderABC456/children"
        assert response.execution_status == "success"


@pytest.mark.asyncio
async def test_list_folder_contents_standard_id(base_client):
    """
    Tests that a standard ID passed to list_folder_contents constructs the default endpoint.
    """
    request = ListFolderContentsRequest(
        folder_id="folderABC456",
        page=1,
        use_cache=False,
        sort_by="object_name",
        sort_order="asc",
    )

    with patch.object(base_client, "_fetch_all_items") as mock_fetch:
        mock_fetch.return_value = []

        await base_client.list_folder_contents(request)

        endpoints = mock_fetch.call_args[0][0]
        assert endpoints[0] == "/me/drive/items/folderABC456/children"


@pytest.mark.asyncio
async def test_read_file_smart_id(base_client, mock_gcs_connector):
    """
    Tests that a SmartID passed to read_file constructs the appropriate metadata and stream endpoints.
    """
    dependencies = SessionContext(
        app_name="test_app", user_id="user1", session_id="session1"
    )
    request = ReadFileRequest(
        file_id="driveXYZ123|fileABC456", dependencies=dependencies, use_cache=False
    )

    mock_instance = mock_gcs_connector.return_value
    mock_instance.upload_stream.return_value = "gs://mock/file.txt"

    with (
        patch.object(base_client, "_get") as mock_get,
        patch("httpx.Client.stream") as mock_stream,
    ):
        mock_get.return_value = {
            "name": "test.txt",
            "file": {"mimeType": "text/plain"},
            "size": 100,
        }

        mock_stream_ctx = MagicMock()
        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        mock_stream_resp.iter_bytes.return_value = iter([b"hello"])
        mock_stream_ctx.__enter__.return_value = mock_stream_resp
        mock_stream.return_value = mock_stream_ctx

        response = await base_client.read_file(request)

        mock_get.assert_called_once_with("/drives/driveXYZ123/items/fileABC456")

        mock_stream.assert_called_once()
        stream_url = mock_stream.call_args[0][1]
        assert stream_url.endswith("/drives/driveXYZ123/items/fileABC456/content")
        assert response.execution_status == "success"
        assert response.gcs_uri == "gs://mock/file.txt"


@pytest.mark.asyncio
async def test_read_file_standard_id(base_client, mock_gcs_connector):
    """
    Tests that a standard ID passed to read_file constructs the default metadata and stream endpoints.
    """
    dependencies = SessionContext(
        app_name="test_app", user_id="user1", session_id="session1"
    )
    request = ReadFileRequest(
        file_id="fileABC456", dependencies=dependencies, use_cache=False
    )

    mock_instance = mock_gcs_connector.return_value
    mock_instance.upload_stream.return_value = "gs://mock/file.txt"

    with (
        patch.object(base_client, "_get") as mock_get,
        patch("httpx.Client.stream") as mock_stream,
    ):
        mock_get.return_value = {
            "name": "test.txt",
            "file": {"mimeType": "text/plain"},
            "size": 100,
        }

        mock_stream_ctx = MagicMock()
        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        mock_stream_resp.iter_bytes.return_value = iter([b"hello"])
        mock_stream_ctx.__enter__.return_value = mock_stream_resp
        mock_stream.return_value = mock_stream_ctx

        response = await base_client.read_file(request)

        mock_get.assert_called_once_with("/me/drive/items/fileABC456")

        mock_stream.assert_called_once()
        stream_url = mock_stream.call_args[0][1]
        assert stream_url.endswith("/me/drive/items/fileABC456/content")
        assert response.execution_status == "success"


def test_format_item_smart_id(base_client):
    """
    Tests that _format_item constructs a SmartID if driveId and id are present.
    """
    raw_item = {
        "id": "file123",
        "name": "shared.txt",
        "file": {"mimeType": "text/plain"},
        "parentReference": {"driveId": "driveXYZ123"},
    }

    formatted = base_client._format_item(raw_item)
    assert formatted["id"] == "driveXYZ123|file123"


@pytest.mark.asyncio
async def test_fetch_all_items_deduplication(base_client):
    """
    Tests that _fetch_all_items correctly deduplicates items that do not have a top-level id
    but instead have an id nested inside remoteItem.
    """
    mock_payload = {
        "value": [
            {"remoteItem": {"id": "shared_id_1", "name": "Shared File 1"}},
            {"id": "regular_id_2", "name": "Regular File 2"},
            {"remoteItem": {"id": "shared_id_1", "name": "Shared File 1 Duplicate"}},
        ]
    }
    with patch.object(base_client, "_get", return_value=mock_payload):
        items = await base_client._fetch_all_items(["/mock/endpoint"], use_cache=False)
        assert len(items) == 2
        assert items[0]["name"] == "Shared File 1"
        assert items[1]["name"] == "Regular File 2"


@pytest.mark.asyncio
async def test_list_folder_contents_shared_with_me_enrichment(base_client):
    """
    Tests that list_folder_contents on SHARED_WITH_ME fetches childCount metadata
    for folders that are missing it.
    """
    request = ListFolderContentsRequest(
        folder_id=MainFolder.SHARED_WITH_ME,
        page=1,
        use_cache=False,
    )

    mock_all_items = [
        {
            "id": "mock_folder_id",
            "name": "Shared Folder",
            "type": ObjectTypeOption.FOLDER,
            "child_count": 0,
            "folder_path": "/",
            "creation_date": "Unknown",
            "last_modified_date": "Unknown",
            "owner": "Unknown",
            "web_url": None,
        }
    ]

    with patch.object(base_client, "_fetch_all_items", return_value=mock_all_items):
        with patch.object(
            base_client,
            "_fetch_file_metadata",
            return_value={"folder": {"childCount": 99}},
        ) as mock_meta:
            response = await base_client.list_folder_contents(request)

            mock_meta.assert_called_once_with("mock_folder_id")
            assert len(response.objects_found) == 1
            # objects_found will be parsed as FolderMetadata, which has total_items_in_folder
            assert response.objects_found[0].total_items_in_folder == 99


@pytest.mark.asyncio
async def test_find_items_synthesize_folder_id(base_client):
    """
    Tests that synthesized folders in find_items receive their actual folder_id
    from the global_path_to_id mapping harvested from all_items.
    """
    request = FindItemsRequest(
        main_folder=MainFolder.SHARED_WITH_ME, item_name="target_file", page=1
    )

    mock_all_items = [
        {
            "id": "real_folder_id",
            "name": "unmatched_folder",
            "type": ObjectTypeOption.FOLDER,
            "folder_path": "/",
            "creation_date": "Unknown",
            "last_modified_date": "Unknown",
            "owner": "Unknown",
            "web_url": None,
        },
        {
            "id": "file_123",
            "name": "target_file.txt",
            "type": ObjectTypeOption.FILE,
            "folder_path": "/unmatched_folder",
            "parent_id": "real_folder_id",
            "creation_date": "Unknown",
            "last_modified_date": "Unknown",
            "owner": "Unknown",
            "web_url": None,
            "mime_type": "text/plain",
        },
        {
            "id": "file_456",
            "name": "target_file_2.txt",
            "type": ObjectTypeOption.FILE,
            "folder_path": "/another_folder",
            "creation_date": "Unknown",
            "last_modified_date": "Unknown",
            "owner": "Unknown",
            "web_url": None,
            "mime_type": "text/plain",
        },
    ]

    with patch.object(base_client, "_fetch_all_items", return_value=mock_all_items):
        response = await base_client.find_items(request)

        assert len(response.objects_found) == 2
        folder_node = next(
            f for f in response.objects_found if f.object_name == "unmatched_folder"
        )
        # It should synthesize the unmatched_folder and populate the real ID
        assert folder_node.object_name == "unmatched_folder"
        assert folder_node.folder_id == "real_folder_id"

        assert len(folder_node.child_objects) == 1
        file_node = folder_node.child_objects[0]
        assert file_node.object_name == "target_file.txt"
