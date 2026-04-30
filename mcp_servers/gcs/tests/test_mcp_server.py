import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

from mcp_servers.gcs.app.mcp_server import (
    _make_gcs_manager,
    create_bucket,
    list_objects,
    list_buckets,
    read_object,
    upload_object,
)
from mcp_servers.gcs.app.config import GCS_API_CONFIG, GCS_SERVER_CONFIG
from mcp_servers.gcs.app.schemas import (
    CreateBucketRequest,
    ListObjectsRequest,
    ListBucketsRequest,
    ReadObjectRequest,
    UploadObjectRequest,
)


@pytest.fixture
def mock_gcs_manager():
    with patch("mcp_servers.gcs.app.mcp_server._make_gcs_manager") as mock:
        yield mock.return_value


def test_mcp_create_bucket_success(mock_gcs_manager):
    mock_gcs_manager.create_bucket.return_value = "my-gcs-bucket"

    request = CreateBucketRequest(
        project_id="test-project",
        bucket_name="my-gcs-bucket",
        location="US",
    )
    result = asyncio.run(create_bucket(request))

    assert result.execution_status == "success"
    assert "Successfully created bucket" in result.execution_message
    mock_gcs_manager.create_bucket.assert_called_once_with(
        "my-gcs-bucket",
        "US",
        "test-project",
    )


def test_mcp_upload_object_success_oauth_flow(mock_gcs_manager):
    mock_blob = MagicMock()
    mock_blob.name = "dest/new_file.pdf"
    mock_gcs_manager.copy_blob.return_value = mock_blob

    request = UploadObjectRequest(
        source_gcs_uri="gs://user-bucket/source/file.pdf",
        destination_bucket="dest-bucket",
        filename="new_file.pdf",
        path_inside_bucket="dest/",
    )
    # Patch _make_gcs_manager inside upload_object to check use_sa
    with patch("mcp_servers.gcs.app.mcp_server._make_gcs_manager") as mock_make:
        mock_make.return_value = mock_gcs_manager
        result = asyncio.run(upload_object(request))
        # Ensure it was called with use_sa=False (default)
        mock_make.assert_called_with(use_sa=False)

    assert result.execution_status == "success"
    assert result.destination_uri == "gs://dest-bucket/dest/new_file.pdf"
    mock_gcs_manager.copy_blob.assert_called_once_with(
        "user-bucket", "source/file.pdf", "dest-bucket", "dest/new_file.pdf"
    )


def test_mcp_upload_object_success_sa_flow(mock_gcs_manager):
    mock_blob = MagicMock()
    mock_blob.name = "ingested_file.zip"
    mock_gcs_manager.copy_blob.return_value = mock_blob

    # Config values: landing_zone_bucket="ai_agent_landing_zone", kb_ingestion_bucket="kb-landing-zone"
    request = UploadObjectRequest(
        source_gcs_uri="gs://ai_agent_landing_zone/incoming/data.zip",
        destination_bucket="kb-landing-zone",
        filename="ingested_file.zip",
    )
    with patch("mcp_servers.gcs.app.mcp_server._make_gcs_manager") as mock_make:
        mock_make.return_value = mock_gcs_manager
        result = asyncio.run(upload_object(request))
        # Ensure it was called with use_sa=True
        mock_make.assert_called_with(use_sa=True)

    assert result.execution_status == "success"
    mock_gcs_manager.copy_blob.assert_called_once()


def test_mcp_upload_object_root_destination(mock_gcs_manager):
    mock_blob = MagicMock()
    mock_blob.name = "root_file.txt"
    mock_gcs_manager.copy_blob.return_value = mock_blob

    # Test with None path
    request_none = UploadObjectRequest(
        source_gcs_uri="gs://src/file.txt",
        destination_bucket="dest",
        filename="root_file.txt",
        path_inside_bucket=None,
    )
    assert request_none.destination_path == "root_file.txt"

    # Test with "/" path
    request_slash = UploadObjectRequest(
        source_gcs_uri="gs://src/file.txt",
        destination_bucket="dest",
        filename="root_file.txt",
        path_inside_bucket="/",
    )
    assert request_slash.destination_path == "root_file.txt"

    # Test with folder path
    request_folder = UploadObjectRequest(
        source_gcs_uri="gs://src/file.txt",
        destination_bucket="dest",
        filename="root_file.txt",
        path_inside_bucket="/my-folder/",
    )
    assert request_folder.destination_path == "my-folder/root_file.txt"


def test_mcp_upload_object_invalid_uri_error():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UploadObjectRequest(
            source_gcs_uri="invalid-uri",
            destination_bucket="dest",
            filename="file.txt",
        )


def test_mcp_list_objects_success(mock_gcs_manager):
    mock_gcs_manager.list_blobs.return_value = ["docs/a.txt", "docs/b.txt"]

    request = ListObjectsRequest(bucket_name="my-gcs-bucket", prefix="docs/")
    result = asyncio.run(list_objects(request))

    assert result.execution_status == "success"
    assert result.objects == ["docs/a.txt", "docs/b.txt"]
    mock_gcs_manager.list_blobs.assert_called_once_with("my-gcs-bucket", "docs/")


def test_mcp_list_buckets_success(mock_gcs_manager):
    mock_gcs_manager.list_buckets.return_value = ["my-gcs-bucket", "my-gcs-backup"]

    request = ListBucketsRequest(project_id="test-project", prefix="my-")
    result = asyncio.run(list_buckets(request))

    assert result.execution_status == "success"
    assert result.buckets == ["my-gcs-bucket", "my-gcs-backup"]
    mock_gcs_manager.list_buckets.assert_called_once_with("my-", "test-project")


def test_mcp_list_objects_authorized_user_success(mock_gcs_manager):
    mock_gcs_manager.list_blobs.return_value = ["docs/a.txt", "docs/b.txt"]

    request = ListObjectsRequest(bucket_name="allowed-bucket", prefix="docs/")
    result = asyncio.run(list_objects(request))

    assert result.execution_status == "success"
    assert result.objects == ["docs/a.txt", "docs/b.txt"]


def test_mcp_read_object_success(mock_gcs_manager):
    mock_blob = MagicMock()
    mock_blob.content_type = "application/pdf"
    mock_blob.size = 1024
    mock_blob.time_created = datetime(2026, 1, 1, 12, 0, 0)
    mock_blob.updated = datetime(2026, 1, 2, 12, 0, 0)
    mock_blob.metadata = {"author": "Antigravity"}

    mock_gcs_manager.get_object_metadata.return_value = mock_blob

    request = ReadObjectRequest(bucket_name="my-bucket", object_name="file.pdf")
    result = asyncio.run(read_object(request))

    assert result.execution_status == "success"
    assert result.gcs_uri == "gs://my-bucket/file.pdf"
    assert result.metadata.mime_type == "application/pdf"
    assert result.metadata.size_bytes == 1024
    assert result.metadata.creation_date == "2026-01-01"
    assert result.metadata.creation_time == "12:00:00"
    assert result.metadata.custom_metadata["author"] == "Antigravity"


def test_mcp_read_object_unauthorized_user_permission_denied(mock_gcs_manager):
    mock_gcs_manager.get_object_metadata.side_effect = Exception(
        "403 Forbidden: caller does not have storage.objects.get access"
    )

    request = ReadObjectRequest(bucket_name="restricted-bucket", object_name="a.txt")
    result = asyncio.run(read_object(request))

    assert result.execution_status == "error"
    assert "Permission Denied" in result.execution_message


def test_mcp_read_object_not_found_normalized_message(mock_gcs_manager):
    mock_gcs_manager.get_object_metadata.side_effect = Exception(
        "404 No such object: restricted-bucket/missing.txt"
    )

    request = ReadObjectRequest(
        bucket_name="restricted-bucket",
        object_name="missing.txt",
    )
    result = asyncio.run(read_object(request))

    assert result.execution_status == "error"
    assert "Object not found" in result.execution_message


def test_make_gcs_manager_uses_context_token_and_configured_scopes():
    token_obj = MagicMock(token="delegated-token")

    with (
        patch(
            "mcp_servers.gcs.app.mcp_server.get_access_token",
            return_value=token_obj,
        ),
        patch(
            "mcp_servers.gcs.app.mcp_server.build_gcs_credentials",
            return_value="creds",
        ) as mock_build_credentials,
        patch(
            "mcp_servers.gcs.app.mcp_server.GCSManager",
            return_value="manager",
        ) as mock_manager,
    ):
        manager = _make_gcs_manager()

    assert manager == "manager"
    mock_build_credentials.assert_called_once_with(
        access_token="delegated-token",
        scopes=GCS_API_CONFIG.read_write_scopes,
    )
    mock_manager.assert_called_once_with(
        "creds", default_project=GCS_SERVER_CONFIG.default_project_id
    )


def test_make_gcs_manager_uses_sa_credentials_when_requested():
    with (
        patch(
            "mcp_servers.gcs.app.mcp_server.build_sa_credentials",
            return_value="sa-creds",
        ) as mock_build_sa,
        patch(
            "mcp_servers.gcs.app.mcp_server.GCSManager",
            return_value="manager",
        ) as mock_manager,
    ):
        manager = _make_gcs_manager(use_sa=True)

    assert manager == "manager"
    mock_build_sa.assert_called_once_with(scopes=GCS_API_CONFIG.read_write_scopes)
    mock_manager.assert_called_once_with(
        "sa-creds", default_project=GCS_SERVER_CONFIG.default_project_id
    )
