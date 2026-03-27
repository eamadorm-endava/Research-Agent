from __future__ import annotations

import asyncio
import logging
from typing import Optional, Sequence

import httpx
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .config import DRIVE_API_CONFIG, DRIVE_AUTH_CONFIG, DRIVE_SERVER_CONFIG
from .drive_client import DriveManager, build_drive_credentials
from .schemas import (
    AuthenticationError,
    CreateFileRequest,
    CreateFileResponse,
    CreateFolderRequest,
    CreateFolderResponse,
    CreateGoogleDocRequest,
    CreateGoogleDocResponse,
    GetFileTextRequest,
    GetFileTextResponse,
    ListFilesRequest,
    ListFilesResponse,
    MoveFileRequest,
    MoveFileResponse,
    RenameFileRequest,
    RenameFileResponse,
    UploadPdfRequest,
    UploadPdfResponse,
)

logger = logging.getLogger(__name__)


class GoogleDriveTokenVerifier(TokenVerifier):
    """
    Validates Google OAuth access tokens for authenticated MCP requests.

        Args:
            None: This verifier uses the bearer token supplied by the current MCP
                request and validates it against Google's token information endpoint.

        Returns:
            None: This class provides token-verification behavior for the MCP server
                and does not return a value when instantiated.
    """

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """
        Verifies a Google OAuth bearer token and converts it into an MCP access token.

            Args:
                token (str): The Google OAuth access token provided by the client for
                    the current authenticated request.

            Returns:
                Optional[AccessToken]: A validated MCP access token containing the
                    client identifier and granted scopes, or None when validation fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{DRIVE_AUTH_CONFIG.google_token_info_url}?access_token={token}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return AccessToken(
                        token=token,
                        client_id=data.get("aud", "unknown"),
                        scopes=data.get("scope", "").split(),
                    )
        except Exception:
            pass
        return None


mcp = FastMCP(
    DRIVE_SERVER_CONFIG.server_name,
    stateless_http=DRIVE_SERVER_CONFIG.stateless_http,
    json_response=DRIVE_SERVER_CONFIG.json_response,
    host=DRIVE_SERVER_CONFIG.default_host,
    port=DRIVE_SERVER_CONFIG.default_port,
    debug=DRIVE_SERVER_CONFIG.debug,
    token_verifier=GoogleDriveTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(DRIVE_AUTH_CONFIG.google_accounts_issuer_url),
        resource_server_url=AnyHttpUrl(
            f"http://{DRIVE_SERVER_CONFIG.default_host}:{DRIVE_SERVER_CONFIG.default_port}"
        ),
    ),
)


@mcp.tool()
async def list_files(request: ListFilesRequest) -> ListFilesResponse:
    """
    Retrieves file and folder metadata from Google Drive that matches specific filter criteria.

        Args:
            request (ListFilesRequest): Search filters including folder names, file names,
                MIME types, date ranges, and sorting instructions.

        Returns:
            ListFilesResponse: A structured collection of matched item metadata,
                aggregate counts, and execution status.
    """
    logger.info(
        "Tool call: list_files(folder_name=%s, file_name=%s, mime_type=%s)",
        request.folder_name,
        request.file_name,
        request.mime_type,
    )
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes)
        files = await asyncio.to_thread(
            manager.list_files,
            folder_name=request.folder_name,
            file_name=request.file_name,
            mime_type=request.mime_type,
            creation_time=request.creation_time,
            last_update=request.last_update,
            order_by=request.order_by,
            max_results=request.max_results,
        )
        total_folders = sum(
            1 for item in files if item.mime_type == DRIVE_API_CONFIG.google_folder
        )
        total_files = len(files) - total_folders
        return ListFilesResponse(
            total_files=total_files,
            total_folders=total_folders,
            files=files,
            execution_status="success",
            execution_message=f"Retrieved {len(files)} Drive items.",
        )
    except AuthenticationError as exc:
        return ListFilesResponse(
            total_files=0,
            total_folders=0,
            files=[],
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return ListFilesResponse(
            total_files=0,
            total_folders=0,
            files=[],
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def get_file_text(request: GetFileTextRequest) -> GetFileTextResponse:
    """
    Extracts readable text content from a Google Drive file identified by its file ID.

        Args:
            request (GetFileTextRequest): The target file identifier and the maximum
                number of characters to return in the extracted text payload.

        Returns:
            GetFileTextResponse: The retrieved document content, related metadata,
                and execution status for the text extraction request.
    """
    logger.info("Tool call: get_file_text(file_id=%s)", request.file_id)
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes)
        document = await asyncio.to_thread(
            manager.get_file_text, file_id=request.file_id
        )
        if len(document.text or "") > request.max_chars:
            document = document.model_copy(
                update={"text": document.text[: request.max_chars] + "\n\n[TRUNCATED]"}
            )
        return GetFileTextResponse(
            file_id=request.file_id,
            max_chars=request.max_chars,
            document=document,
            execution_status="success",
            execution_message=f"Retrieved text for file {request.file_id}.",
        )
    except AuthenticationError as exc:
        return GetFileTextResponse(
            file_id=request.file_id,
            max_chars=request.max_chars,
            document=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return GetFileTextResponse(
            file_id=request.file_id,
            max_chars=request.max_chars,
            document=None,
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def create_google_doc(request: CreateGoogleDocRequest) -> CreateGoogleDocResponse:
    """
    Creates a Google Docs document in Drive using the provided title, content, and folder.

        Args:
            request (CreateGoogleDocRequest): The document title, body text, and
                optional destination folder for the new Google Doc.

        Returns:
            CreateGoogleDocResponse: The created document metadata and the execution
                result for the document creation operation.
    """
    logger.info("Tool call: create_google_doc(title=%s)", request.title)
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.write_doc_scopes)
        file = await asyncio.to_thread(
            manager.create_google_doc_from_text,
            title=request.title,
            content=request.content,
            folder_id=request.folder_id,
        )
        return CreateGoogleDocResponse(
            title=request.title,
            content=request.content,
            folder_id=request.folder_id,
            file=file,
            execution_status="success",
            execution_message=f"Created Google Doc '{request.title}'.",
        )
    except AuthenticationError as exc:
        return CreateGoogleDocResponse(
            title=request.title,
            content=request.content,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return CreateGoogleDocResponse(
            title=request.title,
            content=request.content,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def upload_pdf(request: UploadPdfRequest) -> UploadPdfResponse:
    """
    Generates a PDF from text content and uploads the resulting file to Google Drive.

        Args:
            request (UploadPdfRequest): The PDF title, source text to render, and
                optional destination folder for the uploaded file.

        Returns:
            UploadPdfResponse: The uploaded PDF metadata and the execution result
                for the upload request.
    """
    logger.info("Tool call: upload_pdf(title=%s)", request.title)
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.write_pdf_scopes)
        file = await asyncio.to_thread(
            manager.upload_pdf_from_text,
            title=request.title,
            text=request.text,
            folder_id=request.folder_id,
        )
        return UploadPdfResponse(
            title=request.title,
            text=request.text,
            folder_id=request.folder_id,
            file=file,
            execution_status="success",
            execution_message=f"Uploaded PDF '{request.title}.pdf'.",
        )
    except AuthenticationError as exc:
        return UploadPdfResponse(
            title=request.title,
            text=request.text,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return UploadPdfResponse(
            title=request.title,
            text=request.text,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def create_file(request: CreateFileRequest) -> CreateFileResponse:
    """
    Creates a standard file in Google Drive with the supplied content and MIME type.

        Args:
            request (CreateFileRequest): The file name, file content, MIME type,
                and optional parent folder where the file should be created.

        Returns:
            CreateFileResponse: The created file metadata and the execution result
                for the file creation request.
    """
    logger.info(
        "Tool call: create_file(name=%s, mime_type=%s)", request.name, request.mime_type
    )
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.management_scopes)
        file = await asyncio.to_thread(
            manager.create_file,
            name=request.name,
            content=request.content,
            mime_type=request.mime_type,
            folder_id=request.folder_id,
        )
        return CreateFileResponse(
            name=request.name,
            content=request.content,
            mime_type=request.mime_type,
            folder_id=request.folder_id,
            file=file,
            execution_status="success",
            execution_message=f"Created file '{file.name}'.",
        )
    except AuthenticationError as exc:
        return CreateFileResponse(
            name=request.name,
            content=request.content,
            mime_type=request.mime_type,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return CreateFileResponse(
            name=request.name,
            content=request.content,
            mime_type=request.mime_type,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def create_folder(request: CreateFolderRequest) -> CreateFolderResponse:
    """
    Creates a new folder in Google Drive, optionally inside an existing parent folder.

        Args:
            request (CreateFolderRequest): The folder name and optional parent
                folder identifier for the folder creation request.

        Returns:
            CreateFolderResponse: The created folder metadata and the execution
                result for the folder creation operation.
    """
    logger.info("Tool call: create_folder(name=%s)", request.name)
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.management_scopes)
        file = await asyncio.to_thread(
            manager.create_folder,
            name=request.name,
            folder_id=request.folder_id,
        )
        return CreateFolderResponse(
            name=request.name,
            folder_id=request.folder_id,
            file=file,
            execution_status="success",
            execution_message=f"Created folder '{request.name}'.",
        )
    except AuthenticationError as exc:
        return CreateFolderResponse(
            name=request.name,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return CreateFolderResponse(
            name=request.name,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def move_file(request: MoveFileRequest) -> MoveFileResponse:
    """
    Moves an existing Google Drive item into a different destination folder.

        Args:
            request (MoveFileRequest): The file or folder identifier to move and
                the destination folder identifier that will become its new parent.

        Returns:
            MoveFileResponse: The updated item metadata and the execution result
                for the move operation.
    """
    logger.info(
        "Tool call: move_file(file_id=%s, destination_folder_id=%s)",
        request.file_id,
        request.destination_folder_id,
    )
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.management_scopes)
        file = await asyncio.to_thread(
            manager.move_file,
            file_id=request.file_id,
            destination_folder_id=request.destination_folder_id,
        )
        return MoveFileResponse(
            file_id=request.file_id,
            destination_folder_id=request.destination_folder_id,
            file=file,
            execution_status="success",
            execution_message=f"Moved item '{file.name}' into folder {request.destination_folder_id}.",
        )
    except AuthenticationError as exc:
        return MoveFileResponse(
            file_id=request.file_id,
            destination_folder_id=request.destination_folder_id,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return MoveFileResponse(
            file_id=request.file_id,
            destination_folder_id=request.destination_folder_id,
            file=None,
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def rename_file(request: RenameFileRequest) -> RenameFileResponse:
    """
    Renames an existing file or folder in Google Drive without changing its location.

        Args:
            request (RenameFileRequest): The target item identifier and the new
                display name that should be assigned to the Drive item.

        Returns:
            RenameFileResponse: The renamed item metadata and the execution result
                for the rename operation.
    """
    logger.info(
        "Tool call: rename_file(file_id=%s, new_name=%s)",
        request.file_id,
        request.new_name,
    )
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.management_scopes)
        file = await asyncio.to_thread(
            manager.rename_file,
            file_id=request.file_id,
            new_name=request.new_name,
        )
        return RenameFileResponse(
            file_id=request.file_id,
            new_name=request.new_name,
            file=file,
            execution_status="success",
            execution_message=f"Renamed item to '{request.new_name}'.",
        )
    except AuthenticationError as exc:
        return RenameFileResponse(
            file_id=request.file_id,
            new_name=request.new_name,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}",
        )
    except Exception as exc:
        return RenameFileResponse(
            file_id=request.file_id,
            new_name=request.new_name,
            file=None,
            execution_status="error",
            execution_message=str(exc),
        )


def _make_drive_manager(*, scopes: Sequence[str]) -> DriveManager:
    """
    Builds a Drive manager instance using credentials derived from the current MCP token.

        Args:
            scopes (Sequence[str]): The Google OAuth scopes required for the
                upcoming Drive API operation.

        Returns:
            DriveManager: A Drive manager configured with authenticated credentials
                for the requested scope set.
    """
    access_token = _get_current_token()
    creds = build_drive_credentials(access_token=access_token, scopes=scopes)
    return DriveManager(creds)


def _get_current_token() -> Optional[str]:
    """
    Retrieves the access token associated with the current authenticated MCP request.

        Args:
            None: This helper reads the token from the active MCP authentication
                context and does not accept explicit parameters.

        Returns:
            Optional[str]: The bearer access token for the current request, or None
                when no authenticated token is available.
    """
    token_obj = get_access_token()
    return token_obj.token if token_obj else None
