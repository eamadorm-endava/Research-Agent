import pytest
import asyncio
from unittest.mock import patch

from connectors.cloud_storage.app.mcp_server import (
    create_bucket,
    list_objects,
)
from connectors.cloud_storage.app.schemas import (
    CreateBucketRequest,
    ListObjectsRequest,
    UploadObjectRequest,
)


@pytest.fixture
def mock_gcs_manager():
    with patch("connectors.cloud_storage.app.mcp_server.gcs_manager") as mock:
        yield mock


def test_mcp_create_bucket_success(mock_gcs_manager):
    mock_gcs_manager.create_bucket.return_value = "my-gcs-bucket"

    request = CreateBucketRequest(bucket_name="my-gcs-bucket", location="US")
    result = asyncio.run(create_bucket(request))

    assert result.execution_status == "success"
    assert "Successfully created bucket" in result.execution_message
    mock_gcs_manager.create_bucket.assert_called_once_with("my-gcs-bucket", "US")


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
