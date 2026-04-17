import pytest
import asyncio
from unittest.mock import MagicMock, patch

from mcp_servers.gcs.app.mcp_server import (
    _make_gcs_manager,
    create_bucket,
    list_objects,
    list_buckets,
    read_object,
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


def test_mcp_upload_object_error_when_no_content_source():
    with pytest.raises(ValueError):
        UploadObjectRequest(bucket_name="my-gcs-bucket", object_name="file.txt")


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
