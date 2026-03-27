import unittest
from unittest.mock import MagicMock, patch
from mcp_servers.gcs.app.gcs_client import GCSManager, build_gcs_credentials
from google.cloud.exceptions import GoogleCloudError


class TestGCSManager(unittest.TestCase):
    @patch("google.cloud.storage.Client")
    def setUp(self, mock_client):
        self.mock_client_instance = mock_client.return_value
        self.gcs_manager = GCSManager(creds=MagicMock())

    def test_create_bucket_success(self):
        self.mock_client_instance.create_bucket.return_value.name = "test-bucket"
        result = self.gcs_manager.create_bucket("test-bucket")
        self.assertEqual(result, "test-bucket")
        self.mock_client_instance.create_bucket.assert_called_with(
            "test-bucket", location="US"
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
        self.mock_client_instance.list_buckets.assert_called_with(prefix="my-")


if __name__ == "__main__":
    unittest.main()


@patch("mcp_servers.gcs.app.gcs_client.validate_access_token")
@patch("mcp_servers.gcs.app.gcs_client.Credentials")
def test_build_gcs_credentials_from_access_token(mock_credentials, mock_validate):
    access_token = "ya29.mock-token"

    build_gcs_credentials(access_token=access_token)

    mock_validate.assert_called_once_with(access_token)
    mock_credentials.assert_called_once_with(token=access_token)
