"""ADK tool wrappers for Google Drive.

The functions in this module are designed to be wrapped by `google.adk.tools.FunctionTool`
so the agent can call them.

Authentication behavior:
- In **Gemini Enterprise**, a short-lived user access token is injected into `tool_context.state`
  under the key equal to your `authorizationId`.
- This module reads that token using `GEMINI_ENTERPRISE_AUTH_ID`.

Return values are JSON-serializable dicts/lists suitable for LLM consumption.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .auth import DRIVE_SCOPES, get_drive_credentials
from .connector import DriveConnector

# ADK imports are only required when the agent actually runs.
from google.adk.tools import FunctionTool, ToolContext


# --- internal helpers ---

_STATE_LAST_RESULTS_KEY = "drive_last_results"


def _store_last_results(tool_context: ToolContext | None, items: list[dict[str, Any]]) -> None:
    if tool_context is None:
        return
    try:
        tool_context.state[_STATE_LAST_RESULTS_KEY] = items
    except Exception:
        # State storage is best-effort.
        pass


def _resolve_file_id(file_id_or_index: str, tool_context: ToolContext | None) -> str:
    """Allow `drive_get_file_text` to accept either a file_id or an index into the last search results."""
    if tool_context is None:
        return file_id_or_index
    s = str(file_id_or_index or "").strip()
    if s.isdigit():
        idx = int(s)
        last = None
        try:
            last = tool_context.state.get(_STATE_LAST_RESULTS_KEY)
        except Exception:
            last = None
        if isinstance(last, list) and 0 <= idx < len(last):
            cand = last[idx]
            if isinstance(cand, dict) and isinstance(cand.get("id"), str):
                return cand["id"]
    return s


# --- Tool functions ---


def drive_list_files(
    max_results: int = 10,
    folder_id: str | None = None,
    include_folders: bool = False,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """List recent files from the user's Drive.

    Args:
        max_results: maximum number of files to return.
        folder_id: optional Drive folder ID to restrict results.
        include_folders: include folders in results.

    Returns:
        {"files": [...]} with file metadata.
    """

    creds = get_drive_credentials(tool_context=tool_context, scopes=DRIVE_SCOPES)
    conn = DriveConnector(creds)
    files = conn.list_files(max_results=max_results, folder_id=folder_id, include_folders=include_folders)
    out = [f.to_dict() for f in files]
    _store_last_results(tool_context, out)
    return {"files": out}



def drive_search_files(
    search_text: str | None = None,
    max_results: int = 10,
    folder_id: str | None = None,
    include_folders: bool = False,
    mime_types: Sequence[str] | None = None,
    drive_query: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Search the user's Drive.

    Use `search_text` for a simple search, or `drive_query` to pass a raw Drive query language expression.

    Examples:
        search_text="quarterly report"
        drive_query="name contains 'Q4' and mimeType = 'application/pdf'"

    Returns:
        {"files": [...]} with file metadata.
    """

    creds = get_drive_credentials(tool_context=tool_context, scopes=DRIVE_SCOPES)
    conn = DriveConnector(creds)
    files = conn.search_files(
        search_text=search_text,
        drive_query=drive_query,
        max_results=max_results,
        folder_id=folder_id,
        include_folders=include_folders,
        mime_types=mime_types,
    )
    out = [f.to_dict() for f in files]
    _store_last_results(tool_context, out)
    return {"files": out}



def drive_get_file_text(
    file_id: str,
    max_chars: int = 60000,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Fetch and extract text from a Drive file.

    Args:
        file_id: Drive file ID. You may also pass an integer string index (e.g., "0")
            to refer to the last search/list result.
        max_chars: safety cap for returned text.

    Returns:
        {"document": {...}} including extracted text.
    """

    resolved_id = _resolve_file_id(file_id, tool_context)
    creds = get_drive_credentials(tool_context=tool_context, scopes=DRIVE_SCOPES)
    conn = DriveConnector(creds)
    doc = conn.get_file_text(resolved_id)
    d = doc.to_dict()

    text = d.get("text") or ""
    if isinstance(text, str) and max_chars and len(text) > max_chars:
        d["text"] = text[:max_chars] + "\n\n[TRUNCATED]"

    return {"document": d}


# --- Write-back tools (optional). These require broader scopes. ---


def drive_create_google_doc_from_text(
    title: str,
    content: str,
    folder_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Create a Google Doc in Drive and insert the provided text.

    Requires Drive+Docs write scopes. In Gemini Enterprise, ensure your authorization resource includes:
    - https://www.googleapis.com/auth/drive.file
    - https://www.googleapis.com/auth/documents
    """

    scopes = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents",
    ]
    creds = get_drive_credentials(tool_context=tool_context, scopes=scopes)
    conn = DriveConnector(creds)
    f = conn.create_google_doc_from_text(title=title, content=content, folder_id=folder_id)
    return {"file": f.to_dict()}



def drive_upload_pdf_from_text(
    title: str,
    text: str,
    folder_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Create a PDF from the provided text and upload it to Drive.

    Requires scope:
    - https://www.googleapis.com/auth/drive.file
    """

    scopes = [
        "https://www.googleapis.com/auth/drive.file",
    ]
    creds = get_drive_credentials(tool_context=tool_context, scopes=scopes)
    conn = DriveConnector(creds)
    f = conn.upload_pdf_from_text(title=title, text=text, folder_id=folder_id)
    return {"file": f.to_dict()}


# --- Tool objects (what agent.py should import) ---


drive_list_files_tool = FunctionTool(func=drive_list_files)
drive_search_files_tool = FunctionTool(func=drive_search_files)
drive_get_file_text_tool = FunctionTool(func=drive_get_file_text)

# Configure write tools with confirmation when supported.
try:
    drive_create_google_doc_tool = FunctionTool(
        func=drive_create_google_doc_from_text,
        require_confirmation=True,
    )
except TypeError:
    drive_create_google_doc_tool = FunctionTool(func=drive_create_google_doc_from_text)

try:
    drive_upload_pdf_tool = FunctionTool(
        func=drive_upload_pdf_from_text,
        require_confirmation=True,
    )
except TypeError:
    drive_upload_pdf_tool = FunctionTool(func=drive_upload_pdf_from_text)
