import pytest
from pydantic import ValidationError
from mcp_servers.google_drive.app.schemas import (
    ListFilesRequest,
    CreateFileRequest,
    CreateFolderRequest,
    RenameFileRequest,
    CreateGoogleDocRequest,
)


def test_folder_path_filter_with_spaces_and_accents():
    """Verifies that FOLDER_PATH_FILTER accepts spaces and accents."""
    # Should not raise ValidationError
    req = ListFilesRequest(folder_name="Nutritional Data/2026 Reports/")
    assert req.folder_name == "Nutritional Data/2026 Reports/"

    req = ListFilesRequest(folder_name="Música/Documentação")
    assert req.folder_name == "Música/Documentação"

    req = ListFilesRequest(folder_name="São Paulo/Brasil")
    assert req.folder_name == "São Paulo/Brasil"

    req = ListFilesRequest(folder_name="My Drive/Shared Documents")
    assert req.folder_name == "My Drive/Shared Documents"


def test_other_tools_with_spaces_and_accents():
    """Verifies that other tools also support spaces and accents in titles/names."""
    # CreateFile
    req = CreateFileRequest(name="Relatório de Notas", content="test")
    assert req.name == "Relatório de Notas"

    # CreateFolder
    req = CreateFolderRequest(name="Pasta de Projetos")
    assert req.name == "Pasta de Projetos"

    # Rename
    req = RenameFileRequest(file_id="123", new_name="Nome Alterado")
    assert req.new_name == "Nome Alterado"

    # Google Doc
    req = CreateGoogleDocRequest(title="Resumo da Reunião", content="...")
    assert req.title == "Resumo da Reunião"


def test_folder_path_filter_invalid_chars():
    """Verifies that FOLDER_PATH_FILTER still rejects truly invalid paths."""
    with pytest.raises(ValidationError):
        # Assuming @ is not allowed by \w or \s
        ListFilesRequest(folder_name="Invalid@Char/Folder")


def test_folder_path_filter_basic():
    """Verifies basic path validation still works."""
    req = ListFilesRequest(folder_name="docs/Project-Alpha")
    assert req.folder_name == "docs/Project-Alpha"
