from unittest.mock import MagicMock, patch

import pytest
from mcp_servers.google_drive.app.drive_client import (
    DriveManager,
    DriveFile,
    READ_SCOPES,
    build_drive_credentials,
)


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

    creds = build_drive_credentials(access_token="token-123", scopes=READ_SCOPES)

    assert creds == mock_credentials
    mock_credentials_cls.assert_called_once_with(token="token-123", scopes=READ_SCOPES)


@patch.dict("os.environ", {"DRIVE_USE_ADC": "true"}, clear=False)
@patch("google.auth.default")
def test_build_drive_credentials_adc(mock_auth_default):
    adc_creds = MagicMock()
    mock_auth_default.return_value = (adc_creds, "test-project")

    creds = build_drive_credentials(scopes=READ_SCOPES)

    assert creds == adc_creds
    mock_auth_default.assert_called_once_with(scopes=READ_SCOPES)


@patch.dict("os.environ", {"DRIVE_ALLOW_LOCAL_OAUTH": "true"}, clear=True)
def test_build_drive_credentials_missing_local_oauth_file():
    with pytest.raises(FileNotFoundError):
        build_drive_credentials(scopes=READ_SCOPES)
