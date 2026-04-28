import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from mcp_servers.gcs.app.mcp_server import (
    GoogleGcsTokenVerifier,
    GoogleAccessToken,
    upload_object,
)
from mcp_servers.gcs.app.schemas import UploadObjectRequest
from mcp_servers.gcs.app.gcs_client import GCSManager


@pytest.mark.asyncio
async def test_token_verifier_extracts_email():
    verifier = GoogleGcsTokenVerifier()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "aud": "test_client",
        "scope": "email profile",
        "email": "user@example.com",
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        token_obj = await verifier.verify_token("test_token")

        assert isinstance(token_obj, GoogleAccessToken)
        assert token_obj.email == "user@example.com"


@pytest.mark.asyncio
async def test_upload_object_requires_email():
    request = UploadObjectRequest(
        bucket_name="test-bucket",
        object_name="test.txt",
        source_uri="gs://source-bucket/source.txt",
    )

    # Mock context to return a token WITHOUT email
    with patch("mcp_servers.gcs.app.mcp_server.get_access_token") as mock_get_token:
        mock_get_token.return_value = MagicMock(spec=GoogleAccessToken, email=None)

        response = await upload_object(request)
        assert response.execution_status == "error"
        assert "Mandatory user identity (email) not found" in response.execution_message


@pytest.mark.asyncio
async def test_upload_object_resolves_destination_uri():
    request = UploadObjectRequest(
        destination_uri="gs://dest-bucket/folder/target.txt",
        source_uri="gs://source-bucket/source.txt",
    )

    mock_token = MagicMock(spec=GoogleAccessToken, email="user@example.com")
    mock_blob = MagicMock()
    mock_blob.name = "folder/target.txt"
    mock_blob.content_type = "text/plain"
    mock_blob.metadata = {"user-email": "user@example.com"}

    with (
        patch(
            "mcp_servers.gcs.app.mcp_server.get_access_token", return_value=mock_token
        ),
        patch("mcp_servers.gcs.app.mcp_server._make_gcs_manager") as mock_make_manager,
    ):
        mock_manager = MagicMock(spec=GCSManager)
        mock_manager.parse_gcs_uri.return_value = ("dest-bucket", "folder/target.txt")
        mock_manager.create_object = MagicMock(return_value=mock_blob)
        mock_make_manager.return_value = mock_manager

        response = await upload_object(request)

        assert response.execution_status == "success"
        assert response.bucket_name == "dest-bucket"
        assert response.object_name == "folder/target.txt"
        mock_manager.create_object.assert_called_once()
        _, kwargs = mock_manager.create_object.call_args
        assert kwargs["bucket_name"] == "dest-bucket"
        assert kwargs["object_name"] == "folder/target.txt"
        assert kwargs["user_email"] == "user@example.com"
