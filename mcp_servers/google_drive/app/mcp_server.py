from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

from .config import DRIVE_API_CONFIG, DRIVE_AUTH_CONFIG, DRIVE_SERVER_CONFIG
from .drive_client import DriveManager, build_drive_credentials
from .schemas import (
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

mcp = FastMCP(
    DRIVE_SERVER_CONFIG.server_name,
    stateless_http=DRIVE_SERVER_CONFIG.stateless_http,
    json_response=DRIVE_SERVER_CONFIG.json_response,
    host=DRIVE_SERVER_CONFIG.default_host,
    port=str(DRIVE_SERVER_CONFIG.default_port),
)

_current_http_headers: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    DRIVE_SERVER_CONFIG.header_context_key,
    default=None,
)


class HeaderCaptureMiddleware:
    """Capture inbound HTTP headers so tool functions can access delegated auth."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        context_token = None
        if scope.get("type") == "http":
            headers = {
                raw_key.decode("latin-1").lower(): raw_value.decode("latin-1")
                for raw_key, raw_value in scope.get("headers", [])
            }
            context_token = _current_http_headers.set(headers)
        try:
            await self.app(scope, receive, send)
        finally:
            if context_token is not None:
                _current_http_headers.reset(context_token)


@mcp.tool()
async def list_files(request: ListFilesRequest) -> ListFilesResponse:
    logger.info(
        "Tool call: list_files(max_results=%s, folder_id=%s)",
        request.max_results,
        request.folder_id,
    )
    try:
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes_list())
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
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes_list())
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
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.read_scopes_list())
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
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.write_doc_scopes_list())
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
        manager = _make_drive_manager(scopes=DRIVE_API_CONFIG.write_pdf_scopes_list())
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
    except Exception as exc:
        return UploadPdfResponse(
            title=request.title,
            text=request.text,
            folder_id=request.folder_id,
            file=None,
            execution_status="error",
            execution_message=str(exc),
        )


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())
        yield



def create_app() -> Starlette:
    wrapped_mcp_app = HeaderCaptureMiddleware(mcp.streamable_http_app())
    return Starlette(
        debug=DRIVE_SERVER_CONFIG.debug,
        routes=[Mount(DRIVE_SERVER_CONFIG.route_path, app=wrapped_mcp_app)],
        lifespan=lifespan,
    )



def _make_drive_manager(*, scopes: list[str]) -> DriveManager:
    access_token = _get_delegated_access_token_from_headers()
    creds = build_drive_credentials(access_token=access_token, scopes=scopes)
    return DriveManager(creds)



def _get_current_headers() -> dict[str, str]:
    return _current_http_headers.get() or {}



def _get_delegated_access_token_from_headers() -> str | None:
    header_name = os.getenv(
        DRIVE_AUTH_CONFIG.delegated_token_header_env,
        DRIVE_AUTH_CONFIG.delegated_token_header_default,
    ).lower()
    headers = _get_current_headers()
    return headers.get(header_name)
