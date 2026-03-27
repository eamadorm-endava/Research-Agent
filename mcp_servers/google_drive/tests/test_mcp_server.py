from unittest.mock import MagicMock, patch

import pytest

from mcp_servers.google_drive.app.mcp_server import (
    create_file,
    create_folder,
    create_google_doc,
    get_file_text,
    list_files,
    move_file,
    rename_file,
    upload_pdf,
)
from mcp_servers.google_drive.app.schemas import (
    AuthenticationError,
    CreateFileRequest,
    CreateFolderRequest,
    CreateGoogleDocRequest,
    DriveDocumentModel,
    DriveFileMetadata,
    DriveFileModel,
    FileCreatorModel,
    GetFileTextRequest,
    ListFilesRequest,
    MoveFileRequest,
    RenameFileRequest,
    UploadPdfRequest,
)


@pytest.fixture
def mock_drive_manager():
    """
    Provides a mocked DriveManager instance by patching the factory function.

    Args:
        None

    Returns:
        MagicMock: A mock object representing the DriveManager.
    """
    with patch("mcp_servers.google_drive.app.mcp_server._make_drive_manager") as mock:
        yield mock


@pytest.mark.asyncio
async def test_list_files_success(mock_drive_manager):
    """
    Verifies that list_files successfully retrieves and counts Drive items.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts execution status and file counts.
    """
    manager = MagicMock()
    manager.list_files.return_value = [
        DriveFileMetadata(
            creation_at="2026-03-01T00:00:00Z",
            last_update_at="2026-03-02T00:00:00Z",
            folder_path="/Documents",
            file_name="Doc",
            file_id="1",
            created_by=FileCreatorModel(name="Alice", email="alice@example.com"),
            mime_type="application/pdf",
        )
    ]
    mock_drive_manager.return_value = manager

    result = await list_files(ListFilesRequest(max_results=5))

    assert result.execution_status == "success"
    assert len(result.files) == 1
    assert result.total_files == 1
    assert result.total_folders == 0


@pytest.mark.asyncio
async def test_list_files_auth_error(mock_drive_manager):
    """
    Verifies that list_files gracefully handles authentication failures.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts error status and authentication message.
    """
    mock_drive_manager.side_effect = AuthenticationError("Invalid Token")

    result = await list_files(ListFilesRequest())

    assert result.execution_status == "error"
    assert "Authentication Error" in result.execution_message


@pytest.mark.asyncio
async def test_get_file_text_success(mock_drive_manager):
    """
    Verifies that get_file_text retrieves correct content for a valid file.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts execution status and retrieved text content.
    """
    manager = MagicMock()
    manager.get_file_text.return_value = DriveDocumentModel(
        id="f1",
        name="Notes",
        mimeType="text/plain",
        text="hello world",
        path="/Notes",
    )
    mock_drive_manager.return_value = manager

    result = await get_file_text(GetFileTextRequest(file_id="f1"))

    assert result.execution_status == "success"
    assert result.document.text == "hello world"


@pytest.mark.asyncio
async def test_get_file_text_truncation(mock_drive_manager):
    """
    Verifies that get_file_text correctly truncates output based on max_chars.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts text truncation and the presence of the truncation marker.
    """
    manager = MagicMock()
    manager.get_file_text.return_value = DriveDocumentModel(
        id="f1",
        name="Notes",
        mimeType="text/plain",
        text="This is a long text",
        path="/Notes",
    )
    mock_drive_manager.return_value = manager

    result = await get_file_text(GetFileTextRequest(file_id="f1", max_chars=10))

    assert result.execution_status == "success"
    assert result.document.text == "This is a \n\n[TRUNCATED]"


@pytest.mark.asyncio
async def test_create_google_doc_success(mock_drive_manager):
    """
    Verifies that create_google_doc correctly routes requests to create a new Doc.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts the created file's ID and success status.
    """
    manager = MagicMock()
    manager.create_google_doc_from_text.return_value = DriveFileModel(
        id="doc1",
        name="Summary",
        mimeType="application/vnd.google-apps.document",
        path="/Summary",
    )
    mock_drive_manager.return_value = manager

    result = await create_google_doc(
        CreateGoogleDocRequest(title="Summary", content="hello")
    )

    assert result.execution_status == "success"
    assert result.file.id == "doc1"


@pytest.mark.asyncio
async def test_upload_pdf_success(mock_drive_manager):
    """
    Verifies that upload_pdf correctly routes requests to render and upload a PDF.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts the uploaded PDF's file name and success status.
    """
    manager = MagicMock()
    manager.upload_pdf_from_text.return_value = DriveFileModel(
        id="pdf1",
        name="Summary.pdf",
        mimeType="application/pdf",
        path="/Summary.pdf",
    )
    mock_drive_manager.return_value = manager

    result = await upload_pdf(UploadPdfRequest(title="Summary", text="hello"))

    assert result.execution_status == "success"
    assert result.file.id == "pdf1"


@pytest.mark.asyncio
async def test_create_file_success(mock_drive_manager):
    """
    Verifies that create_file successfully creates a standard file with content.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts the created file name and execution status.
    """
    manager = MagicMock()
    manager.create_file.return_value = DriveFileModel(
        id="txt1",
        name="notes.txt",
        mimeType="text/plain",
        path="/notes.txt",
    )
    mock_drive_manager.return_value = manager

    result = await create_file(CreateFileRequest(name="notes", content="hello"))

    assert result.execution_status == "success"
    assert result.file.name == "notes.txt"


@pytest.mark.asyncio
async def test_create_folder_success(mock_drive_manager):
    """
    Verifies that create_folder successfully creates a new Drive folder.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts the created folder ID and success status.
    """
    manager = MagicMock()
    manager.create_folder.return_value = DriveFileModel(
        id="folder1",
        name="Project",
        mimeType="application/vnd.google-apps.folder",
        path="/Project",
    )
    mock_drive_manager.return_value = manager

    result = await create_folder(CreateFolderRequest(name="Project"))

    assert result.execution_status == "success"
    assert result.file.id == "folder1"


@pytest.mark.asyncio
async def test_move_file_success(mock_drive_manager):
    """
    Verifies that move_file correctly updates an item's parent location.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts the updated file path and success status.
    """
    manager = MagicMock()
    manager.move_file.return_value = DriveFileModel(
        id="file1",
        name="notes.txt",
        mimeType="text/plain",
        path="/Archive/notes.txt",
    )
    mock_drive_manager.return_value = manager

    result = await move_file(
        MoveFileRequest(file_id="file1", destination_folder_id="folder2")
    )

    assert result.execution_status == "success"
    assert result.file.path == "/Archive/notes.txt"


@pytest.mark.asyncio
async def test_rename_file_success(mock_drive_manager):
    """
    Verifies that rename_file correctly updates an item's display name.

    Args:
        mock_drive_manager (MagicMock): Mocked DriveManager instance.

    Returns:
        None: Asserts the renamed file name and success status.
    """
    manager = MagicMock()
    manager.rename_file.return_value = DriveFileModel(
        id="file1",
        name="renamed.txt",
        mimeType="text/plain",
        path="/renamed.txt",
    )
    mock_drive_manager.return_value = manager

    result = await rename_file(
        RenameFileRequest(file_id="file1", new_name="renamed.txt")
    )

    assert result.execution_status == "success"
    assert result.file.name == "renamed.txt"
