import pytest
import asyncio
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


def test_mcp_upload_object_schema_validation():
    # Valid request
    UploadObjectRequest(
        source_uri="gs://bucket/file.txt",
        destination_bucket="target-bucket",
    )

    # Missing mandatory source_uri
    with pytest.raises(ValueError):
        UploadObjectRequest(destination_bucket="target-bucket")


def test_mcp_upload_object_success(mock_gcs_manager):
    mock_blob = MagicMock()
    mock_blob.name = "new_file.txt"
    mock_gcs_manager.copy_object.return_value = mock_blob

    # Mock token and email extraction
    with (
        patch("mcp_servers.gcs.app.mcp_server._get_current_token", return_value="tok"),
        patch(
            "mcp_servers.gcs.app.mcp_server._fetch_user_email",
            return_value="user@example.com",
        ),
    ):
        request = UploadObjectRequest(
            source_uri="gs://landing/source.txt",
            destination_bucket="kb-bucket",
            name_of_the_file="renamed",
        )
        result = asyncio.run(upload_object(request))

    assert result.execution_status == "success"
    assert "Successfully ingested source.txt" in result.execution_message
    assert result.gcs_uri == "gs://kb-bucket/new_file.txt"

    # Verify metadata injection
    mock_gcs_manager.copy_object.assert_called_once()
    args, _ = mock_gcs_manager.copy_object.call_args
    assert args[3]["uploader"] == "user@example.com"


def test_mcp_upload_object_credential_switching():
    # Test switching to SA for KB bucket
    with (
        patch("mcp_servers.gcs.app.mcp_server._get_current_token", return_value="tok"),
        patch(
            "mcp_servers.gcs.app.mcp_server._fetch_user_email",
            return_value="user@example.com",
        ),
        patch("mcp_servers.gcs.app.mcp_server._make_sa_gcs_manager") as mock_sa_manager,
        patch("mcp_servers.gcs.app.mcp_server._make_gcs_manager") as mock_user_manager,
    ):
        mock_sa_manager.return_value.copy_object.return_value.name = "saved.txt"
        mock_user_manager.return_value.copy_object.return_value.name = "saved.txt"

        # Case 1: KB Bucket -> Should use SA
        request_kb = UploadObjectRequest(
            source_uri="gs://land/file.txt",
            destination_bucket=GCS_SERVER_CONFIG.kb_landing_zone,
        )
        asyncio.run(upload_object(request_kb))
        mock_sa_manager.assert_called_once()

        # Case 2: Other Bucket -> Should use OAuth
        request_other = UploadObjectRequest(
            source_uri="gs://land/file.txt",
            destination_bucket="personal-bucket",
        )
        asyncio.run(upload_object(request_other))
        mock_user_manager.assert_called_once()


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


def test_mcp_read_object_unauthorized_user_permission_denied(mock_gcs_manager):
    mock_gcs_manager.download_object_as_bytes.side_effect = Exception(
        "403 Forbidden: caller does not have storage.objects.get access"
    )

    request = ReadObjectRequest(bucket_name="restricted-bucket", object_name="a.txt")
    result = asyncio.run(read_object(request))

    assert result.execution_status == "error"
    assert "Permission Denied" in result.execution_message


def test_mcp_read_object_not_found_normalized_message(mock_gcs_manager):
    mock_gcs_manager.download_object_as_bytes.side_effect = Exception(
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
