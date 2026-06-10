from unittest.mock import MagicMock, patch
import pytest
from app.onedrive_client import OneDriveClient


@pytest.fixture
def mock_access_token():
    return "mock_token"


@pytest.fixture
def mock_gcs_connector():
    with patch("app.onedrive_client.GCSConnector") as mock:
        yield mock


def test_init_no_token():
    with pytest.raises(ValueError):
        OneDriveClient("")


def test_list_files_root(mock_access_token, mock_gcs_connector):
    client = OneDriveClient(mock_access_token)
    with patch("httpx.Client.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": [{"name": "file1.txt"}]}
        mock_get.return_value = mock_response

        items = client.list_files()

        mock_get.assert_called_once()
        assert (
            mock_get.call_args[0][0]
            == "https://graph.microsoft.com/v1.0/me/drive/root/children"
        )
        assert len(items) == 1
        assert items[0]["name"] == "file1.txt"


def test_list_files_401(mock_access_token, mock_gcs_connector):
    client = OneDriveClient(mock_access_token)
    with patch("httpx.Client.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with pytest.raises(ValueError):
            client.list_files()


def test_search_files(mock_access_token, mock_gcs_connector):
    client = OneDriveClient(mock_access_token)
    with patch("httpx.Client.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": [{"name": "search_result.txt"}]}
        mock_get.return_value = mock_response

        items = client.search_files("query")

        mock_get.assert_called_once()
        assert "search(q='query')" in mock_get.call_args[0][0]
        assert len(items) == 1
        assert items[0]["name"] == "search_result.txt"


def test_read_file(mock_access_token, mock_gcs_connector):
    client = OneDriveClient(mock_access_token)

    # Mock the GCSConnector upload_stream to return a specific URI
    mock_instance = mock_gcs_connector.return_value
    mock_instance.upload_stream.return_value = "gs://mock-landing-zone/folder/file.pdf"

    with (
        patch("httpx.Client.get") as mock_get,
        patch("httpx.Client.stream") as mock_stream,
    ):
        # Mock metadata response
        mock_meta_response = MagicMock()
        mock_meta_response.status_code = 200
        mock_meta_response.json.return_value = {
            "name": "test.pdf",
            "file": {"mimeType": "application/pdf"},
        }
        mock_get.return_value = mock_meta_response

        # Mock stream response context manager
        mock_stream_ctx = MagicMock()
        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        mock_stream_resp.iter_bytes.return_value = iter([b"chunk1", b"chunk2"])
        mock_stream_ctx.__enter__.return_value = mock_stream_resp
        mock_stream.return_value = mock_stream_ctx

        result = client.read_file("123", "test_app", "user_1", "sess_1")

        assert result["gcs_uri"] == "gs://mock-landing-zone/folder/file.pdf"
        assert result["mime_type"] == "application/pdf"
        assert result["filename"] == "test.pdf"
        mock_instance.upload_stream.assert_called_once()
