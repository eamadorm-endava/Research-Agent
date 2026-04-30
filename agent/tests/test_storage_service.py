import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from google.genai import types
from agent.core_agent.storage.service import StorageService


@pytest.mark.asyncio
async def test_save_artifact_with_file_data_performs_copy():
    # Setup
    mock_bucket = MagicMock()
    mock_bucket.name = "artifact-bucket"

    with patch("google.cloud.storage.Client") as mock_client_class:
        mock_client = mock_client_class.return_value
        # The StorageService init calls self.bucket which we need to mock
        with patch.object(StorageService, "__init__", return_value=None):
            service = StorageService()
            service.bucket = mock_bucket

            # Mock parent methods
            service._list_versions = MagicMock(return_value=[1, 2])
            service._get_blob_name = MagicMock(
                return_value="app/user/session/file/v3/content"
            )
            service.ensure_uploader_permissions = AsyncMock()

            # Request
            artifact_part = types.Part(
                file_data=types.FileData(
                    file_uri="gs://source-bucket/source-file.pdf",
                    mime_type="application/pdf",
                )
            )

            # Execute
            version = await service.save_artifact(
                app_name="test-app",
                user_id="user@example.com",
                session_id="session-123",
                filename="target.pdf",
                artifact=artifact_part,
            )

            # Assertions
            assert version == 3
            # Check if copy_blob was called on the destination bucket
            mock_bucket.copy_blob.assert_called_once()

            # Verify source extraction
            mock_client.bucket.assert_called_with("source-bucket")

            # Verify metadata patch
            mock_bucket.blob.assert_called_with("app/user/session/file/v3/content")
            mock_bucket.blob.return_value.patch.assert_called_once()
            assert mock_bucket.blob.return_value.content_type == "application/pdf"


@pytest.mark.asyncio
async def test_save_artifact_with_bytes_calls_super():
    mock_bucket = MagicMock()
    mock_bucket.name = "artifact-bucket"

    with patch(
        "google.adk.artifacts.gcs_artifact_service.GcsArtifactService.save_artifact",
        new_callable=AsyncMock,
    ) as mock_super_save:
        mock_super_save.return_value = 5

        with patch.object(StorageService, "__init__", return_value=None):
            service = StorageService()
            service.bucket = mock_bucket
            service._get_blob_name = MagicMock(return_value="path/to/blob")
            service.ensure_uploader_permissions = AsyncMock()

            artifact_part = types.Part(text="hello")

            version = await service.save_artifact(
                app_name="test-app",
                user_id="user@example.com",
                session_id="session-123",
                filename="target.txt",
                artifact=artifact_part,
            )

            assert version == 5
            mock_super_save.assert_called_once()
            mock_bucket.copy_blob.assert_not_called()
