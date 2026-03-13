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

from typing import Any, Sequence

from google.adk.tools import FunctionTool, ToolContext

from .auth import get_drive_credentials
from .config import DRIVE_SCOPE_CONFIG, DRIVE_TOOL_RUNTIME_CONFIG
from .connector import DriveConnector


# --- internal helpers ---


def _store_last_results(tool_context: ToolContext | None, items: list[dict[str, Any]]) -> None:
    if tool_context is None:
        return
    try:
        tool_context.state[DRIVE_TOOL_RUNTIME_CONFIG.state_last_results_key] = items
    except Exception:
        pass



def _resolve_file_id(file_id_or_index: str, tool_context: ToolContext | None) -> str:
    """Allow `drive_get_file_text` to accept either a file_id or an index into the last search results."""
    if tool_context is None:
        return file_id_or_index
    normalized_input = str(file_id_or_index or "").strip()
    if normalized_input.isdigit():
        idx = int(normalized_input)
        last = None
        try:
            last = tool_context.state.get(DRIVE_TOOL_RUNTIME_CONFIG.state_last_results_key)
        except Exception:
            last = None
        if isinstance(last, list) and 0 <= idx < len(last):
            candidate = last[idx]
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
                return candidate["id"]
    return normalized_input


# --- Tool functions ---


def drive_list_files(
    max_results: int = DRIVE_TOOL_RUNTIME_CONFIG.default_max_results,
    folder_id: str | None = None,
    include_folders: bool = False,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """List recent files from the user's Drive."""

    creds = get_drive_credentials(
        tool_context=tool_context,
        scopes=DRIVE_SCOPE_CONFIG.read_only_list(),
    )
    connector = DriveConnector(creds)
    files = connector.list_files(
        max_results=max_results,
        folder_id=folder_id,
        include_folders=include_folders,
    )
    output = [drive_file.to_dict() for drive_file in files]
    _store_last_results(tool_context, output)
    return {"files": output}



def drive_search_files(
    search_text: str | None = None,
    max_results: int = DRIVE_TOOL_RUNTIME_CONFIG.default_max_results,
    folder_id: str | None = None,
    include_folders: bool = False,
    mime_types: Sequence[str] | None = None,
    drive_query: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Search the user's Drive."""

    creds = get_drive_credentials(
        tool_context=tool_context,
        scopes=DRIVE_SCOPE_CONFIG.read_only_list(),
    )
    connector = DriveConnector(creds)
    files = connector.search_files(
        search_text=search_text,
        drive_query=drive_query,
        max_results=max_results,
        folder_id=folder_id,
        include_folders=include_folders,
        mime_types=mime_types,
    )
    output = [drive_file.to_dict() for drive_file in files]
    _store_last_results(tool_context, output)
    return {"files": output}



def drive_get_file_text(
    file_id: str,
    max_chars: int = DRIVE_TOOL_RUNTIME_CONFIG.default_max_text_chars,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Fetch and extract text from a Drive file."""

    resolved_id = _resolve_file_id(file_id, tool_context)
    creds = get_drive_credentials(
        tool_context=tool_context,
        scopes=DRIVE_SCOPE_CONFIG.read_only_list(),
    )
    connector = DriveConnector(creds)
    document = connector.get_file_text(resolved_id)
    output = document.to_dict()

    text = output.get("text") or ""
    if isinstance(text, str) and max_chars and len(text) > max_chars:
        output["text"] = text[:max_chars] + "\n\n[TRUNCATED]"

    return {"document": output}



def drive_create_google_doc_from_text(
    title: str,
    content: str,
    folder_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Create a Google Doc in Drive and insert the provided text."""

    creds = get_drive_credentials(
        tool_context=tool_context,
        scopes=DRIVE_SCOPE_CONFIG.write_document_list(),
    )
    connector = DriveConnector(creds)
    drive_file = connector.create_google_doc_from_text(
        title=title,
        content=content,
        folder_id=folder_id,
    )
    return {"file": drive_file.to_dict()}



def drive_upload_pdf_from_text(
    title: str,
    text: str,
    folder_id: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Create a PDF from the provided text and upload it to Drive."""

    creds = get_drive_credentials(
        tool_context=tool_context,
        scopes=DRIVE_SCOPE_CONFIG.write_pdf_list(),
    )
    connector = DriveConnector(creds)
    drive_file = connector.upload_pdf_from_text(
        title=title,
        text=text,
        folder_id=folder_id,
    )
    return {"file": drive_file.to_dict()}


# --- Tool objects (what agent.py should import) ---


drive_list_files_tool = FunctionTool(func=drive_list_files)
drive_search_files_tool = FunctionTool(func=drive_search_files)
drive_get_file_text_tool = FunctionTool(func=drive_get_file_text)

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
