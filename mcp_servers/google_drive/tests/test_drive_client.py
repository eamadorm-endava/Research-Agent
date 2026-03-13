from unittest.mock import MagicMock, patch

from mcp_servers.google_drive.app.config import DRIVE_API_CONFIG
from mcp_servers.google_drive.app.drive_client import (
    DriveManager,
    DriveFile,
    build_drive_credentials,
    validate_access_token,
)
from mcp_servers.google_drive.app.schemas import AuthenticationError


@patch("mcp_servers.google_drive.app.drive_client.build")
def test_drive_manager_list_files(mock_build):
    mock_drive = MagicMock()
    mock_build.return_value = mock_drive
    mock_drive.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "file_1",
                "name": "Quarterly Report",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-03-10T12:00:00Z",
                "webViewLink": "https://drive.google.com/file/d/file_1/view",
            }
        ]
    }

    manager = DriveManager(creds=MagicMock())
    files = manager.list_files(max_results=5)

    assert files == [
        DriveFile(
            id="file_1",
            name="Quarterly Report",
            mimeType="application/pdf",
            modifiedTime="2026-03-10T12:00:00Z",
            webViewLink="https://drive.google.com/file/d/file_1/view",
        )
    ]
    mock_drive.files.return_value.list.assert_called_once()


@patch("mcp_servers.google_drive.app.drive_client.validate_access_token")
@patch("mcp_servers.google_drive.app.drive_client.Credentials")
def test_build_drive_credentials_from_access_token(mock_credentials_cls, mock_validate):
    mock_credentials = MagicMock()
    mock_credentials_cls.return_value = mock_credentials
    mock_validate.return_value = {
        "scope": " ".join(DRIVE_API_CONFIG.read_scopes_list())
    }

    creds = build_drive_credentials(
        access_token="abc123",
        scopes=DRIVE_API_CONFIG.read_scopes_list(),
    )

    assert creds is mock_credentials
    mock_validate.assert_called_once_with("abc123", DRIVE_API_CONFIG.read_scopes_list())
    mock_credentials_cls.assert_called_once_with(
        token="abc123",
        scopes=DRIVE_API_CONFIG.read_scopes_list(),
    )


def test_validate_access_token_success():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "scope": "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file"
        }

        token_info = validate_access_token(
            "valid_token", ["https://www.googleapis.com/auth/drive.readonly"]
        )
        assert "scope" in token_info


def test_validate_access_token_invalid():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 401
        mock_get.return_value.json.return_value = {"error_description": "Invalid Value"}

        import pytest

        with pytest.raises(AuthenticationError) as excinfo:
            validate_access_token("invalid_token")
        assert "Invalid OAuth token" in str(excinfo.value)


def test_validate_access_token_missing_scopes():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "scope": "https://www.googleapis.com/auth/userinfo.email"
        }

        import pytest

        with pytest.raises(AuthenticationError) as excinfo:
            validate_access_token(
                "valid_token", ["https://www.googleapis.com/auth/drive.readonly"]
            )
        assert "Token is missing required scopes" in str(excinfo.value)
