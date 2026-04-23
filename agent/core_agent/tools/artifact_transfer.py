import asyncio
import base64
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import google.auth
from google.auth.transport.requests import Request
from google.adk.tools.tool_context import ToolContext
from loguru import logger

from ..config import GCS_MCP_CONFIG
from ..security import get_ge_oauth_token, get_id_token

_ARTIFACT_STATE_KEY = "latest_uploaded_artifacts"


def _coerce_bytes(blob_data: Any) -> bytes:
    """Normalizes blob payloads coming from ADK artifacts into raw bytes."""
    if blob_data is None:
        raise ValueError("The selected artifact does not contain any payload bytes.")
    if isinstance(blob_data, bytes):
        return blob_data
    if isinstance(blob_data, bytearray):
        return bytes(blob_data)
    if isinstance(blob_data, memoryview):
        return blob_data.tobytes()
    if isinstance(blob_data, str):
        try:
            return base64.b64decode(blob_data, validate=True)
        except Exception:
            return blob_data.encode("utf-8")
    raise TypeError(f"Unsupported artifact payload type: {type(blob_data)!r}")


async def _load_uploaded_artifact(
    tool_context: ToolContext,
    artifact_name: Optional[str],
) -> tuple[str, Any]:
    """Resolves and loads the target artifact for landing-zone transfer."""
    available_artifacts = await tool_context.list_artifacts()
    if not available_artifacts:
        raise ValueError(
            "No uploaded artifacts are available in this session. "
            "Upload a document before calling the landing-zone transfer tool."
        )

    tracked_artifacts = tool_context.state.get(_ARTIFACT_STATE_KEY) or []
    if artifact_name:
        selected_artifact = artifact_name
    elif tracked_artifacts:
        selected_artifact = tracked_artifacts[-1]
    elif len(available_artifacts) == 1:
        selected_artifact = available_artifacts[0]
    else:
        raise ValueError(
            "Multiple artifacts are available in this session. "
            "Provide artifact_name explicitly to choose one. "
            f"Available artifacts: {', '.join(sorted(available_artifacts))}"
        )

    if selected_artifact not in available_artifacts:
        raise ValueError(
            f"Artifact '{selected_artifact}' is not available in this session. "
            f"Available artifacts: {', '.join(sorted(available_artifacts))}"
        )

    artifact_part = await tool_context.load_artifact(selected_artifact)
    if artifact_part is None:
        raise ValueError(f"Artifact '{selected_artifact}' could not be loaded.")

    return selected_artifact, artifact_part


def _extract_artifact_payload(
    artifact_name: str, artifact_part: Any
) -> tuple[str, bytes, str]:
    """Extracts filename, bytes, and MIME type from an ADK artifact part."""
    inline_data = getattr(artifact_part, "inline_data", None)
    if inline_data is None:
        raise ValueError(
            f"Artifact '{artifact_name}' is not stored as inline file content and cannot "
            "be transferred with the current landing-zone bridge."
        )

    file_name = getattr(inline_data, "display_name", None) or artifact_name
    mime_type = (
        getattr(inline_data, "mime_type", None) or mimetypes.guess_type(file_name)[0]
    )
    artifact_bytes = _coerce_bytes(getattr(inline_data, "data", None))
    return file_name, artifact_bytes, mime_type or "application/octet-stream"


def _build_object_name(file_name: str, explicit_object_name: Optional[str]) -> str:
    """Determines the final destination object name in the landing zone."""
    if explicit_object_name:
        return explicit_object_name

    prefix = (GCS_MCP_CONFIG.LANDING_ZONE_PREFIX or "").strip("/")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    normalized_name = Path(file_name).name
    generated_name = f"{timestamp}-{normalized_name}"
    if not prefix:
        return generated_name
    return f"{prefix}/{generated_name}"


def _build_metadata(
    *,
    artifact_name: str,
    original_file_name: str,
    project_name: Optional[str],
    trust_level: Optional[str],
    version_label: Optional[str],
    pii_intent: Optional[str],
    additional_metadata: Optional[dict[str, str]],
) -> dict[str, str]:
    """Builds the metadata payload sent to the GCS MCP server."""
    metadata: dict[str, str] = {
        "source-artifact": artifact_name,
        "original-file-name": original_file_name,
        "upload-channel": "adk-chat-ui",
    }

    optional_pairs = {
        "project": project_name,
        "trust-level": trust_level,
        "version-label": version_label,
        "pii-intent": pii_intent,
    }
    for key, value in optional_pairs.items():
        if value is not None and str(value).strip():
            metadata[key] = str(value).strip()

    for key, value in (additional_metadata or {}).items():
        if value is None:
            continue
        metadata[str(key)] = str(value)

    return metadata


def _get_runtime_access_token(tool_context: ToolContext) -> str:
    """Resolves the delegated OAuth token for GCS MCP calls."""
    auth_id = GCS_MCP_CONFIG.GEMINI_GOOGLE_AUTH_ID
    if auth_id:
        delegated_token = get_ge_oauth_token(tool_context, auth_id)
        if delegated_token:
            return delegated_token

    credentials, _ = google.auth.default()
    credentials.refresh(Request())
    access_token = getattr(credentials, "token", None)
    if access_token:
        return access_token

    raise ValueError(
        "Unable to resolve a delegated OAuth token for the GCS MCP upload call."
    )


def _build_headers(tool_context: ToolContext) -> dict[str, str]:
    """Builds the headers required for direct JSON-RPC calls to the GCS MCP server."""
    endpoint_audience = GCS_MCP_CONFIG.URL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {_get_runtime_access_token(tool_context)}",
    }

    id_token = get_id_token(endpoint_audience)
    if id_token:
        headers["X-Serverless-Authorization"] = f"Bearer {id_token}"

    return headers


def _post_jsonrpc(
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any] | None:
    """Performs a blocking JSON-RPC POST to the target MCP endpoint."""
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8").strip()
        if not body:
            return None
        return json.loads(body)


async def _call_gcs_upload(
    tool_context: ToolContext,
    upload_request: dict[str, Any],
) -> dict[str, Any]:
    """Calls the GCS MCP upload tool over JSON-RPC."""
    endpoint = urllib.parse.urljoin(GCS_MCP_CONFIG.URL, GCS_MCP_CONFIG.ENDPOINT)
    headers = _build_headers(tool_context)

    initialize_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "research-agent-artifact-transfer",
                "version": "0.1.0",
            },
        },
    }
    initialized_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    upload_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "upload_object",
            "arguments": {"request": upload_request},
        },
    }

    try:
        await asyncio.to_thread(_post_jsonrpc, endpoint, initialize_payload, headers)
        await asyncio.to_thread(_post_jsonrpc, endpoint, initialized_payload, headers)
        response = await asyncio.to_thread(
            _post_jsonrpc, endpoint, upload_payload, headers
        )
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"The GCS MCP upload call failed with HTTP {exc.code}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Unable to reach the GCS MCP endpoint: {exc.reason}"
        ) from exc

    if response is None:
        raise RuntimeError("The GCS MCP upload call returned an empty response.")
    if response.get("error"):
        raise RuntimeError(json.dumps(response["error"], sort_keys=True))

    result = response.get("result") or {}
    structured = result.get("structuredContent") or result
    if structured.get("execution_status") == "error":
        raise RuntimeError(structured.get("execution_message", "Upload failed."))
    return structured


async def transfer_uploaded_artifact_to_landing_zone(
    artifact_name: Optional[str] = None,
    bucket_name: Optional[str] = None,
    object_name: Optional[str] = None,
    project_name: Optional[str] = None,
    trust_level: Optional[str] = None,
    version_label: Optional[str] = None,
    pii_intent: Optional[str] = None,
    additional_metadata: Optional[dict[str, str]] = None,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Transfers the latest uploaded chat artifact into the Knowledge Base landing-zone bucket.

    The tool loads a session artifact that originated from a chat upload, preserves the
    file bytes and MIME type, forwards the payload to the GCS MCP upload tool, and
    attaches dynamic metadata for the downstream ingestion pipeline.

    Args:
        artifact_name: Optional session artifact name to transfer. When omitted, the
            most recently uploaded artifact tracked in session state is used.
        bucket_name: Optional destination bucket. Defaults to the configured
            Knowledge Base landing-zone bucket.
        object_name: Optional destination object path. When omitted, a timestamped
            object name is generated from the original filename.
        project_name: Optional business project name to store as custom metadata.
        trust_level: Optional trust-level metadata value such as published or wip.
        version_label: Optional version metadata captured during ingestion.
        pii_intent: Optional user-declared PII intent metadata.
        additional_metadata: Optional free-form metadata keys and values to attach.
        tool_context: ADK tool context injected by the runtime.

    Returns:
        dict[str, Any]: A structured summary of the landing-zone transfer outcome.
    """
    if tool_context is None:
        raise ValueError("tool_context is required for artifact transfer.")

    destination_bucket = bucket_name or GCS_MCP_CONFIG.LANDING_ZONE_BUCKET
    if not destination_bucket:
        raise ValueError(
            "No landing-zone bucket is configured. Set KB_LANDING_ZONE_BUCKET or "
            "provide bucket_name explicitly."
        )

    selected_artifact, artifact_part = await _load_uploaded_artifact(
        tool_context, artifact_name
    )
    original_file_name, artifact_bytes, mime_type = _extract_artifact_payload(
        selected_artifact, artifact_part
    )
    destination_object = _build_object_name(original_file_name, object_name)
    metadata = _build_metadata(
        artifact_name=selected_artifact,
        original_file_name=original_file_name,
        project_name=project_name,
        trust_level=trust_level,
        version_label=version_label,
        pii_intent=pii_intent,
        additional_metadata=additional_metadata,
    )

    upload_request = {
        "bucket_name": destination_bucket,
        "object_name": destination_object,
        "content_base64": base64.b64encode(artifact_bytes).decode("ascii"),
        "content_type": mime_type,
        "metadata": metadata,
        "user_identity_context": {
            "adk_user_id": tool_context.user_id,
            "adk_session_id": tool_context.session_id,
            "adk_app_name": tool_context.app_name,
        },
    }

    logger.info(
        "Transferring uploaded artifact '%s' to gs://%s/%s",
        selected_artifact,
        destination_bucket,
        destination_object,
    )
    structured = await _call_gcs_upload(tool_context, upload_request)

    return {
        "artifact_name": selected_artifact,
        "original_file_name": original_file_name,
        "bucket_name": destination_bucket,
        "object_name": destination_object,
        "gcs_uri": f"gs://{destination_bucket}/{destination_object}",
        "content_type": structured.get("content_type", mime_type),
        "metadata": structured.get("metadata", metadata),
        "user_email": structured.get("user_email"),
        "execution_status": structured.get("execution_status", "success"),
        "execution_message": structured.get(
            "execution_message",
            "Artifact transferred to the landing zone successfully.",
        ),
    }
