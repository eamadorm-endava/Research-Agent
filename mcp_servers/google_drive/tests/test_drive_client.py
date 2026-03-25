from unittest.mock import MagicMock, patch

import pytest

from mcp_servers.google_drive.app.config import DRIVE_API_CONFIG
from mcp_servers.google_drive.app.drive_client import (
    DriveManager,
    build_drive_credentials,
    validate_access_token,
)
from mcp_servers.google_drive.app.schemas import AuthenticationError, DriveMimeType, ListFilesSortField, SortDirection


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
                "createdTime": "2026-03-01T12:00:00Z",
                "webViewLink": "https://drive.google.com/file/d/file_1/view",
                "parents": [],
                "owners": [{"displayName": "Alice", "emailAddress": "alice@example.com"}],
                "size": "42",
                "version": "7",
            }
        ]
    }

    manager = DriveManager(creds=MagicMock())
    files = manager.list_files(max_results=5)

    assert files[0].file_name == "Quarterly Report"
    assert files[0].file_id == "file_1"
    assert files[0].folder_path == "/"
    assert files[0].mime_type == "application/pdf"
    assert files[0].created_by.name == "Alice"
    mock_drive.files.return_value.list.assert_called_once()


@patch("mcp_servers.google_drive.app.drive_client.build")
def test_drive_manager_resolves_nested_path(mock_build):
    mock_drive = MagicMock()
    mock_build.return_value = mock_drive

    get_execute = mock_drive.files.return_value.get.return_value.execute
    get_execute.side_effect = [
        {"id": "parent_1", "name": "Projects", "parents": ["parent_0"]},
        {"id": "parent_0", "name": "Documents", "parents": []},
    ]
    mock_drive.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "file_1",
                "name": "notes.txt",
                "mimeType": "text/plain",
                "parents": ["parent_1"],
            }
        ]
    }

    manager = DriveManager(creds=MagicMock())
    files = manager.list_files(max_results=1)

    assert files[0].folder_path == "/Documents/Projects"


@patch("mcp_servers.google_drive.app.drive_client.build")
def test_drive_manager_list_files_with_folder_path_and_sort(mock_build):
    mock_drive = MagicMock()
    mock_build.return_value = mock_drive
    mock_drive.files.return_value.list.return_value.execute.side_effect = [
        {"files": [{"id": "folder_1", "name": "Projects", "parents": []}]},
        {
            "files": [
                {
                    "id": "file_2",
                    "name": "b.txt",
                    "mimeType": DriveMimeType.PLAIN_TEXT.value,
                    "createdTime": "2026-03-02T00:00:00Z",
                    "modifiedTime": "2026-03-03T00:00:00Z",
                    "parents": ["folder_1"],
                    "owners": [],
                },
                {
                    "id": "file_1",
                    "name": "a.txt",
                    "mimeType": DriveMimeType.PLAIN_TEXT.value,
                    "createdTime": "2026-03-01T00:00:00Z",
                    "modifiedTime": "2026-03-04T00:00:00Z",
                    "parents": ["folder_1"],
                    "owners": [],
                },
            ]
        },
    ]
    mock_drive.files.return_value.get.return_value.execute.return_value = {
        "id": "folder_1",
        "name": "Projects",
        "parents": [],
    }

    manager = DriveManager(creds=MagicMock())
    files = manager.list_files(
        folder_name="Projects/",
        mime_type=DriveMimeType.PLAIN_TEXT,
        order_by={ListFilesSortField.FILE_NAME: SortDirection.ASC},
        max_results=10,
    )

    assert [item.file_name for item in files] == ["a.txt", "b.txt"]


@patch("mcp_servers.google_drive.app.drive_client.validate_access_token")
@patch("mcp_servers.google_drive.app.drive_client.Credentials")
def test_build_drive_credentials_from_access_token(mock_credentials_cls, mock_validate):
    mock_credentials = MagicMock()
    mock_credentials_cls.return_value = mock_credentials
    mock_validate.return_value = {"scope": " ".join(DRIVE_API_CONFIG.read_scopes)}

    creds = build_drive_credentials(
        access_token="abc123",
        scopes=DRIVE_API_CONFIG.read_scopes,
    )

    assert creds is mock_credentials
    mock_validate.assert_called_once_with("abc123", DRIVE_API_CONFIG.read_scopes)
    mock_credentials_cls.assert_called_once_with(
        token="abc123",
        scopes=DRIVE_API_CONFIG.read_scopes,
    )


def test_validate_access_token_success():
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "scope": DRIVE_API_CONFIG.drive_scope
        }

        token_info = validate_access_token(
            "valid_token", [DRIVE_API_CONFIG.drive_scope]
        )
        assert "scope" in token_info


def test_validate_access_token_full_drive_scope_satisfies_documents_scope():
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"scope": DRIVE_API_CONFIG.drive_scope}

        token_info = validate_access_token(
            "valid_token", ["https://www.googleapis.com/auth/documents"]
        )
        assert token_info["scope"] == DRIVE_API_CONFIG.drive_scope


def test_validate_access_token_invalid():
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 401
        mock_get.return_value.json.return_value = {"error_description": "Invalid Value"}

        with pytest.raises(AuthenticationError) as excinfo:
            validate_access_token("invalid_token")
        assert "Invalid OAuth token" in str(excinfo.value)


def test_validate_access_token_missing_scopes():
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "scope": "https://www.googleapis.com/auth/userinfo.email"
        }

        with pytest.raises(AuthenticationError) as excinfo:
            validate_access_token("valid_token", [DRIVE_API_CONFIG.drive_scope])
        assert "Token is missing required scopes" in str(excinfo.value)
