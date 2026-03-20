from unittest.mock import MagicMock, patch

import pytest

from mcp_servers.google_drive.app.mcp_server import (
    create_google_doc,
    get_file_text,
    list_files,
    search_files,
    upload_pdf,
)
from mcp_servers.google_drive.app.schemas import (
    CreateGoogleDocRequest,
    DriveDocumentModel,
    DriveFileModel,
    GetFileTextRequest,
    ListFilesRequest,
    SearchFilesRequest,
    UploadPdfRequest,
)


@pytest.fixture
def mock_drive_manager():
    with patch("mcp_servers.google_drive.app.mcp_server._make_drive_manager") as mock:
        yield mock


@pytest.mark.asyncio
async def test_list_files_success(mock_drive_manager):
    manager = MagicMock()
    manager.list_files.return_value = [
        DriveFileModel(id="1", name="Doc", mimeType="application/pdf")
    ]
    mock_drive_manager.return_value = manager

    result = await list_files(ListFilesRequest(max_results=5))

    assert result.execution_status == "success"
    assert len(result.files) == 1


@pytest.mark.asyncio
async def test_search_files_error(mock_drive_manager):
    mock_drive_manager.side_effect = RuntimeError("missing credentials")

    result = await search_files(SearchFilesRequest(search_text="budget"))

    assert result.execution_status == "error"
    assert "missing credentials" in result.execution_message


@pytest.mark.asyncio
async def test_get_file_text_success(mock_drive_manager):
    manager = MagicMock()
    manager.get_file_text.return_value = DriveDocumentModel(
        id="f1",
        name="Notes",
        mimeType="text/plain",
        text="hello world",
    )
    mock_drive_manager.return_value = manager

    result = await get_file_text(GetFileTextRequest(file_id="f1"))

    assert result.execution_status == "success"
    assert result.document is not None
    assert result.document.text == "hello world"


@pytest.mark.asyncio
async def test_create_google_doc_success(mock_drive_manager):
    manager = MagicMock()
    manager.create_google_doc_from_text.return_value = DriveFileModel(
        id="doc1",
        name="Summary",
        mimeType="application/vnd.google-apps.document",
    )
    mock_drive_manager.return_value = manager

    result = await create_google_doc(
        CreateGoogleDocRequest(title="Summary", content="hello")
    )

    assert result.execution_status == "success"
    assert result.file is not None
    assert result.file.id == "doc1"


@pytest.mark.asyncio
async def test_upload_pdf_success(mock_drive_manager):
    manager = MagicMock()
    manager.upload_pdf_from_text.return_value = DriveFileModel(
        id="pdf1",
        name="Summary.pdf",
        mimeType="application/pdf",
    )
    mock_drive_manager.return_value = manager

    result = await upload_pdf(UploadPdfRequest(title="Summary", text="hello"))

    assert result.execution_status == "success"
    assert result.file is not None
    assert result.file.id == "pdf1"
