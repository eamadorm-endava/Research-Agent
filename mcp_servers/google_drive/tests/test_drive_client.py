from unittest.mock import MagicMock, patch

from mcp_servers.google_drive.app.config import DRIVE_API_CONFIG
from mcp_servers.google_drive.app.drive_client import DriveManager, DriveFile, build_drive_credentials


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


@patch("mcp_servers.google_drive.app.drive_client.Credentials")
def test_build_drive_credentials_from_access_token(mock_credentials_cls):
    mock_credentials = MagicMock()
    mock_credentials_cls.return_value = mock_credentials

    creds = build_drive_credentials(
        access_token="abc123",
        scopes=DRIVE_API_CONFIG.read_scopes_list(),
    )

    assert creds is mock_credentials
    mock_credentials_cls.assert_called_once_with(
        token="abc123",
        scopes=DRIVE_API_CONFIG.read_scopes_list(),
    )
