from unittest.mock import MagicMock, patch

import pytest
from mcp_servers.google_drive.app.config import DRIVE_API_CONFIG
from mcp_servers.google_drive.app.drive_client import (
    DriveManager,
    _escape_q,
    _extract_text_from_pdf_bytes,
    build_drive_credentials,
    validate_access_token,
)


@pytest.fixture
def mock_drive_service():
    """
    Standard fixture to mock the Google Drive API service builder.

    Args:
        None

    Returns:
        MagicMock: A mock for the Google API build function.
    """
    with patch("mcp_servers.google_drive.app.drive_client.build") as mock:
        yield mock


def test_drive_manager_init(mock_drive_service):
    """
    Verifies that DriveManager initializes with correct API version and credentials.

    Args:
        mock_drive_service (MagicMock): Mocked Google API build function.

    Returns:
        None: Asserts build parameters and credentials assignment.
    """
    creds = MagicMock()
    manager = DriveManager(creds)
    assert manager.creds == creds
    mock_drive_service.assert_called_once_with(
        "drive", "v3", credentials=creds, cache_discovery=False
    )


@patch("mcp_servers.google_drive.app.drive_client.validate_access_token")
@patch("mcp_servers.google_drive.app.drive_client.Credentials")
def test_build_drive_credentials(mock_creds, mock_validate):
    """
    Verifies credential construction logic for both success and Failure cases.

    Args:
        mock_creds (MagicMock): Mocked Google Credentials class.
        mock_validate (MagicMock): Mocked token validation function.

    Returns:
        None: Asserts validation calls and RuntimeError on missing tokens.
    """
    # Success case
    build_drive_credentials(access_token="tok", validate=True)
    mock_validate.assert_called_once()
    mock_creds.assert_called_once_with(token="tok", scopes=DRIVE_API_CONFIG.read_scopes)

    # Failure case
    with pytest.raises(RuntimeError):
        build_drive_credentials(access_token=None)


def test_drive_manager_list_files_simple(mock_drive_service):
    """
    Verifies basic file listing and path resolution from the Drive API.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts file metadata conversion and resolved folder path.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive

    # Mocking list response
    mock_drive.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "1",
                "name": "doc1.txt",
                "mimeType": "text/plain",
                "createdTime": "2026-03-01T00:00:00Z",
                "modifiedTime": "2026-03-02T00:00:00Z",
                "parents": ["root"],
                "owners": [{"displayName": "Alice", "emailAddress": "alice@gmail.com"}],
            }
        ]
    }

    # Mocking path resolution for the file
    mock_drive.files.return_value.get.return_value.execute.return_value = {
        "id": "root",
        "name": "My Drive",
        "parents": [],
    }

    manager = DriveManager(None)
    items = manager.list_files(max_results=1)

    assert len(items) == 1
    assert items[0].file_name == "doc1.txt"
    assert items[0].folder_path == "/My Drive"


def test_drive_manager_get_file_text_google_doc(mock_drive_service):
    """
    Verifies text extraction from Google Docs via the export endpoint.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts the text content and successful export call.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive

    # Mock metadata payload and path resolution calls
    # Note: Both call .get(...).execute()
    mock_get_call = mock_drive.files.return_value.get.return_value
    mock_get_call.execute.side_effect = [
        # First call: metadata payload
        {
            "id": "f1",
            "name": "Google Doc",
            "mimeType": DRIVE_API_CONFIG.google_doc,
            "parents": ["p1"],
            "owners": [],
        },
        # Second call: path resolution (parent folder)
        {"id": "p1", "name": "Folder1", "parents": []},
    ]

    # Mock export
    mock_drive.files.return_value.export.return_value.execute.return_value = (
        b"doc content"
    )

    manager = DriveManager(None)
    doc = manager.get_file_text("f1")

    assert doc.text == "doc content"
    assert mock_drive.files.return_value.export.called


def test_drive_manager_create_folder(mock_drive_service):
    """
    Verifies that folder creation correctly sets metadata and parent relationships.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts name, mimeType, and parent ID in the API request.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive
    mock_drive.files.return_value.create.return_value.execute.return_value = {
        "id": "new_folder_id"
    }

    manager = DriveManager(None)

    # Mock get_file (which is called at the end of create_folder)
    with patch.object(DriveManager, "get_file") as mock_get_file:
        mock_get_file.return_value = MagicMock()
        manager.create_folder(name="Test Folder", folder_id="parent_id")

        mock_drive.files.return_value.create.assert_called_once()
        _, kwargs = mock_drive.files.return_value.create.call_args
        assert kwargs["body"]["name"] == "Test Folder"
        assert kwargs["body"]["mimeType"] == DRIVE_API_CONFIG.google_folder
        assert kwargs["body"]["parents"] == ["parent_id"]


def test_drive_manager_move_file(mock_drive_service):
    """
    Verifies that file moving correctly toggles parent folder IDs.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts added and removed parent IDs in the API update.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive

    # Mock get current parents
    mock_drive.files.return_value.get.return_value.execute.return_value = {
        "id": "f1",
        "parents": ["old_p"],
    }
    mock_drive.files.return_value.update.return_value.execute.return_value = {}

    manager = DriveManager(None)
    with patch.object(DriveManager, "get_file"):
        manager.move_file(file_id="f1", destination_folder_id="new_p")

        mock_drive.files.return_value.update.assert_called_once()
        _, kwargs = mock_drive.files.return_value.update.call_args
        assert kwargs["addParents"] == "new_p"
        assert kwargs["removeParents"] == "old_p"


def test_extract_text_from_pdf_error_handling():
    """
    Verifies graceful failure marker when PDF parsing encounters invalid bytes.

    Args:
        None (Uses raw bytes input).

    Returns:
        None: Asserts presence of error marker in the result string.
    """
    # Corrupt or invalid bytes
    text = _extract_text_from_pdf_bytes(b"not a pdf")
    assert "[PDF_TEXT_EXTRACTION_FAILED" in text


def test_validate_access_token_v3_endpoint():
    """
    Verifies that OAuth token validation correctly checks scope permissions.

    Args:
        None (Patches httpx.Client).

    Returns:
        None: Asserts scope presence in the validation response.
    """
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "scope": DRIVE_API_CONFIG.drive_scope
        }

        info = validate_access_token("tok", [DRIVE_API_CONFIG.drive_scope])
        assert info["scope"] == DRIVE_API_CONFIG.drive_scope


def test_resolve_folder_id_by_path(mock_drive_service):
    """
    Verifies recursive path resolution by segments to find a folder ID.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts segments are resolved in order and correct final ID.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive

    # Mock path discovery: root -> FolderA -> FolderB
    mock_list_call = mock_drive.files.return_value.list.return_value
    mock_list_call.execute.side_effect = [
        {"files": [{"id": "id_a", "name": "FolderA"}]},
        {"files": [{"id": "id_b", "name": "FolderB"}]},
    ]

    manager = DriveManager(None)
    folder_id = manager._resolve_folder_id_by_path("Folder A/Folder B")

    assert folder_id == "id_b"
    assert mock_list_call.execute.call_count == 2

    # Check that it searched with the correct name including space
    # The .list() method is what receives the query string 'q'
    mock_list_method = mock_drive.files.return_value.list
    _, kwargs = mock_list_method.call_args_list[0]
    assert "name = 'Folder A'" in kwargs["q"]


def test_drive_manager_create_file(mock_drive_service):
    """
    Verifies that standard file creation includes media content and correct name.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts file name, media body presence, and success status.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive
    mock_drive.files.return_value.create.return_value.execute.return_value = {
        "id": "f123"
    }

    manager = DriveManager(None)
    with patch.object(DriveManager, "get_file"):
        manager.create_file(name="notes", content="hello world", mime_type="text/plain")

        mock_drive.files.return_value.create.assert_called_once()
        _, kwargs = mock_drive.files.return_value.create.call_args
        assert kwargs["body"]["name"] == "notes.txt"
        assert kwargs["media_body"] is not None


def test_drive_manager_upload_pdf_from_text(mock_drive_service):
    """
    Verifies that PDF generation and upload correctly labels the file name.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts the resulting file includes the .pdf extension.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive
    mock_drive.files.return_value.create.return_value.execute.return_value = {
        "id": "p123"
    }

    manager = DriveManager(None)
    with patch.object(DriveManager, "get_file"):
        manager.upload_pdf_from_text(title="Report", text="PDF Content")

        mock_drive.files.return_value.create.assert_called_once()
        _, kwargs = mock_drive.files.return_value.create.call_args
        assert kwargs["body"]["name"] == "Report.pdf"


def test_drive_manager_rename_file(mock_drive_service):
    """
    Verifies that file renaming emits a metadata update with the new name.

    Args:
        mock_drive_service (MagicMock): Mocked Google API service.

    Returns:
        None: Asserts the new name is passed in the update request body.
    """
    mock_drive = MagicMock()
    mock_drive_service.return_value = mock_drive
    mock_drive.files.return_value.update.return_value.execute.return_value = {}

    manager = DriveManager(None)
    with patch.object(DriveManager, "get_file"):
        manager.rename_file(file_id="f1", new_name="new_name")

        mock_drive.files.return_value.update.assert_called_once()
        _, kwargs = mock_drive.files.return_value.update.call_args
        assert kwargs["body"]["name"] == "new_name"


def test_escape_q_various():
    """
    Verifies that Drive API query strings are correctly escaped for special chars.

    Args:
        None (Uses string utilities).

    Returns:
        None: Asserts escaped outputs for single quotes and null values.
    """
    assert _escape_q("don't stop") == "don\\'t stop"
    assert _escape_q("no quotes") == "no quotes"
    assert _escape_q(None) == ""
