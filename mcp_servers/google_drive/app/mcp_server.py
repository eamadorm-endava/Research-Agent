from __future__ import annotations

import asyncio
import logging

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
    CreateGoogleDocRequest,
    CreateGoogleDocResponse,
    GetFileTextRequest,
    GetFileTextResponse,
    ListFilesRequest,
    ListFilesResponse,
    SearchFilesRequest,
    SearchFilesResponse,
    UploadPdfRequest,
    UploadPdfResponse,
)

logger = logging.getLogger(__name__)


class GoogleDriveTokenVerifier(TokenVerifier):
    """Verifies a Google OAuth access token."""

    async def verify_token(self, token: str) -> AccessToken | None:
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
    logger.info(
        "Tool call: list_files(max_results=%s, folder_id=%s)",
        request.max_results,
        request.folder_id,
    )
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes)
        files = await asyncio.to_thread(
            manager.list_files,
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
        )
        return ListFilesResponse(
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
            files=files,
            execution_status="success",
            execution_message=f"Found {len(files)} files.",
        )
    except AuthenticationError as exc:
        auth_url = _get_auth_url(scopes=DRIVE_API_CONFIG.read_scopes)
        url_hint = f" Please authorize access here: {auth_url}" if auth_url else ""
        return ListFilesResponse(
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
            files=[],
            execution_status="error",
            execution_message=f"Authentication Error: {exc}.{url_hint}",
        )
    except Exception as exc:
        return ListFilesResponse(
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
            files=[],
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def search_files(request: SearchFilesRequest) -> SearchFilesResponse:
    logger.info(
        "Tool call: search_files(search_text=%s, drive_query=%s)",
        request.search_text,
        request.drive_query,
    )
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes)
        files = await asyncio.to_thread(
            manager.search_files,
            search_text=request.search_text,
            drive_query=request.drive_query,
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
            mime_types=request.mime_types,
        )
        return SearchFilesResponse(
            search_text=request.search_text,
            drive_query=request.drive_query,
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
            mime_types=request.mime_types,
            files=files,
            execution_status="success",
            execution_message=f"Found {len(files)} matching files.",
        )
    except AuthenticationError as exc:
        auth_url = _get_auth_url(scopes=DRIVE_API_CONFIG.read_scopes)
        url_hint = f" Please authorize access here: {auth_url}" if auth_url else ""
        return SearchFilesResponse(
            search_text=request.search_text,
            drive_query=request.drive_query,
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
            mime_types=request.mime_types,
            files=[],
            execution_status="error",
            execution_message=f"Authentication Error: {exc}.{url_hint}",
        )
    except Exception as exc:
        return SearchFilesResponse(
            search_text=request.search_text,
            drive_query=request.drive_query,
            max_results=request.max_results,
            folder_id=request.folder_id,
            include_folders=request.include_folders,
            mime_types=request.mime_types,
            files=[],
            execution_status="error",
            execution_message=str(exc),
        )


@mcp.tool()
async def get_file_text(request: GetFileTextRequest) -> GetFileTextResponse:
    logger.info("Tool call: get_file_text(file_id=%s)", request.file_id)
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes)
        document = await asyncio.to_thread(manager.get_file_text, request.file_id)
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
        auth_url = _get_auth_url(scopes=DRIVE_API_CONFIG.read_scopes)
        url_hint = f" Please authorize access here: {auth_url}" if auth_url else ""
        return GetFileTextResponse(
            file_id=request.file_id,
            max_chars=request.max_chars,
            document=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}.{url_hint}",
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
        auth_url = _get_auth_url(scopes=DRIVE_API_CONFIG.write_doc_scopes)
        url_hint = f" Please authorize access here: {auth_url}" if auth_url else ""
        return CreateGoogleDocResponse(
            title=request.title,
            content=request.content,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}.{url_hint}",
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
        auth_url = _get_auth_url(scopes=DRIVE_API_CONFIG.write_pdf_scopes)
        url_hint = f" Please authorize access here: {auth_url}" if auth_url else ""
        return UploadPdfResponse(
            title=request.title,
            text=request.text,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=f"Authentication Error: {exc}.{url_hint}",
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


def _make_drive_manager(*, scopes: list[str]) -> DriveManager:
    access_token = _get_current_token()
    creds = build_drive_credentials(
        access_token=access_token, scopes=scopes, validate=False
    )
    return DriveManager(creds)


def _get_current_token() -> str | None:
    # Use native MCP access token which is extracted/validated by middleware
    token_obj = get_access_token()
    return token_obj.token if token_obj else None


def _get_auth_url(scopes: list[str]) -> str:
    """Construct the Google Drive authorization URL if client info is available."""
    client_id = DRIVE_AUTH_CONFIG.google_oauth_client_id
    redirect_uri = DRIVE_AUTH_CONFIG.google_oauth_redirect_uri

    if not (client_id and redirect_uri):
        return ""

    import urllib.parse

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
    }
    return (
        f"{DRIVE_AUTH_CONFIG.google_oauth2_auth_url}?{urllib.parse.urlencode(params)}"
    )
