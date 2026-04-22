import unittest
from unittest.mock import MagicMock, patch
from mcp_servers.gcs.app.config import GCS_API_CONFIG
from mcp_servers.gcs.app.gcs_client import (
    GCSManager,
    build_gcs_credentials,
    detect_default_project_id,
    validate_access_token,
)
from google.cloud.exceptions import GoogleCloudError


class TestGCSManager(unittest.TestCase):
    @patch("google.cloud.storage.Client")
    def setUp(self, mock_client):
        self.mock_client_instance = mock_client.return_value
        self.gcs_manager = GCSManager(creds=MagicMock(), default_project="test-project")

    def test_create_bucket_success(self):
        self.mock_client_instance.create_bucket.return_value.name = "test-bucket"
        result = self.gcs_manager.create_bucket("test-bucket")
        self.assertEqual(result, "test-bucket")
        self.mock_client_instance.create_bucket.assert_called_with(
            "test-bucket", location="US", project="test-project"
        )

    def test_create_bucket_failure(self):
        self.mock_client_instance.create_bucket.side_effect = GoogleCloudError(
            "Creation failed"
        )
        with self.assertRaises(GoogleCloudError):
            self.gcs_manager.create_bucket("fail-bucket")

    def test_upload_object_string_content(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        self.mock_client_instance.get_bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.name = "test.txt"
        mock_blob.content_type = "text/plain"

        result = self.gcs_manager.create_object(
            "test-bucket", "test.txt", content="hello"
        )

        self.assertEqual(result.name, "test.txt")
        mock_blob.upload_from_string.assert_called_with(
            "hello", content_type="text/plain"
        )

    def test_upload_object_bytes_content(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        self.mock_client_instance.get_bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.name = "data.bin"
        mock_blob.content_type = "application/octet-stream"

        result = self.gcs_manager.create_object(
            "test-bucket", "data.bin", content=b"\x00\x01"
        )

        self.assertEqual(result.name, "data.bin")
        mock_blob.upload_from_string.assert_called_with(
            b"\x00\x01", content_type="application/octet-stream"
        )

    @patch("os.path.exists")
    @patch("mimetypes.guess_type")
    def test_upload_object_local_path(self, mock_guess, mock_exists):
        mock_exists.return_value = True
        mock_guess.return_value = ("image/png", None)
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        self.mock_client_instance.get_bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.name = "remote.png"
        mock_blob.content_type = "image/png"

        result = self.gcs_manager.create_object(
            "test-bucket", "remote.png", local_path="/tmp/local.png"
        )

        self.assertEqual(result.name, "remote.png")
        mock_blob.upload_from_filename.assert_called_with(
            "/tmp/local.png", content_type="image/png"
        )

    def test_download_object_as_bytes(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        self.mock_client_instance.get_bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_bytes.return_value = b"test content"

        result = self.gcs_manager.download_object_as_bytes("test-bucket", "doc.txt")

        self.assertEqual(result, b"test content")
        mock_blob.download_as_bytes.assert_called_once()

    def test_update_object_metadata(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        self.mock_client_instance.get_bucket.return_value = mock_bucket
        mock_bucket.get_blob.return_value = mock_blob
        mock_blob.metadata = {"key": "old"}
        mock_blob.content_type = "text/plain"

        self.gcs_manager.update_object_metadata(
            "test-bucket",
            "doc.txt",
            {"key": "new", "content_type": "text/markdown", "custom": "val"},
        )

        self.assertEqual(mock_blob.content_type, "text/markdown")
        self.assertEqual(mock_blob.metadata, {"key": "new", "custom": "val"})
        mock_blob.patch.assert_called_once()

    def test_list_blobs(self):
        mock_bucket = MagicMock()
        mock_blob1 = MagicMock(name="file1.txt")
        mock_blob1.name = "file1.txt"
        mock_blob2 = MagicMock(name="file2.txt")
        mock_blob2.name = "file2.txt"

        self.mock_client_instance.get_bucket.return_value = mock_bucket
        self.mock_client_instance.list_blobs.return_value = [mock_blob1, mock_blob2]

        result = self.gcs_manager.list_blobs("test-bucket", prefix="data/")

        self.assertEqual(result, ["file1.txt", "file2.txt"])
        self.mock_client_instance.list_blobs.assert_called_with(
            mock_bucket, prefix="data/"
        )

    def test_list_buckets(self):
        mock_bucket1 = MagicMock()
        mock_bucket1.name = "my-bucket-a"
        mock_bucket2 = MagicMock()
        mock_bucket2.name = "my-bucket-b"

        self.mock_client_instance.list_buckets.return_value = [
            mock_bucket1,
            mock_bucket2,
        ]

        result = self.gcs_manager.list_buckets(prefix="my-")

        self.assertEqual(result, ["my-bucket-a", "my-bucket-b"])
        self.mock_client_instance.list_buckets.assert_called_with(
            prefix="my-", project="test-project"
        )


if __name__ == "__main__":
    unittest.main()


@patch("mcp_servers.gcs.app.gcs_client.validate_access_token")
@patch("mcp_servers.gcs.app.gcs_client.Credentials")
def test_build_gcs_credentials_from_access_token(mock_credentials, mock_validate):
    access_token = "ya29.mock-token"

    build_gcs_credentials(access_token=access_token)

    expected_scopes = list(GCS_API_CONFIG.read_write_scopes)

    mock_validate.assert_called_once_with(access_token, expected_scopes)
    mock_credentials.assert_called_once_with(
        token=access_token,
        scopes=expected_scopes,
    )


def test_validate_access_token_accepts_cloud_platform_scope_for_gcs_operations():
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "scope": GCS_API_CONFIG.cloud_platform_scope
        }

        info = validate_access_token("tok", GCS_API_CONFIG.read_write_scopes)

    assert info["scope"] == GCS_API_CONFIG.cloud_platform_scope


@patch("mcp_servers.gcs.app.gcs_client.storage.Client")
@patch(
    "mcp_servers.gcs.app.gcs_client.detect_default_project_id",
    return_value="adc-project",
)
def test_gcs_manager_uses_adc_project_when_env_default_missing(
    mock_detect_project, mock_client
):
    GCSManager(creds=MagicMock(), default_project=None)

    mock_detect_project.assert_called_once_with()
    mock_client.assert_called_once()
    _, kwargs = mock_client.call_args
    assert kwargs["project"] == "adc-project"


@patch(
    "mcp_servers.gcs.app.gcs_client.google.auth.default",
    return_value=(MagicMock(), "adc-project"),
)
def test_detect_default_project_id_returns_adc_project(mock_google_auth_default):
    detect_default_project_id.cache_clear()

    assert detect_default_project_id() == "adc-project"

    mock_google_auth_default.assert_called_once_with()


@patch(
    "mcp_servers.gcs.app.gcs_client.google.auth.default",
    side_effect=Exception("metadata unavailable"),
)
def test_detect_default_project_id_returns_none_when_detection_fails(
    mock_google_auth_default,
):
    detect_default_project_id.cache_clear()

    assert detect_default_project_id() is None

    mock_google_auth_default.assert_called_once_with()
