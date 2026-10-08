"""Authenticated server-to-server API calls and bounded SSE parsing."""

import json
import os
import urllib.request
from urllib.parse import urlencode, urlsplit

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000/api").rstrip("/")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def request_headers(assertion: str | None) -> dict[str, str]:
    """Forward the original signed user assertion separately from the Cloud Run token."""
    headers = {}
    if assertion:
        headers["X-Goog-IAP-JWT-Assertion"] = assertion
    if os.getenv("ENVIRONMENT") == "development":
        return headers
    if not assertion:
        raise RuntimeError(
            "IAP authentication is missing. Open OSIRIS through its public URL."
        )
    parsed = urlsplit(API_URL)
    audience = f"{parsed.scheme}://{parsed.netloc}"
    query = urlencode({"audience": audience})
    metadata_request = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        f"service-accounts/default/identity?{query}",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(metadata_request, timeout=5) as response:
        token = response.read().decode()
    headers["Authorization"] = f"Bearer {token}"
    return headers


def chat_events(message: str, session_id: str | None, assertion: str | None):
    """Stream well-formed events with bounded connect/read timeouts."""
    with requests.post(
        f"{API_URL}/chat/",
        json={"message": message, "session_id": session_id},
        headers=request_headers(assertion),
        stream=True,
        timeout=(10, 300),
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(chunk_size=1, decode_unicode=True):
            if line and line.startswith("data: "):
                yield json.loads(line[6:])


def upload_file(uploaded_file, assertion: str | None) -> str:
    """Upload with the exact signed content type and length; return its private URI."""
    content_type = uploaded_file.type or "application/octet-stream"
    response = requests.post(
        f"{API_URL}/upload/generate-url",
        headers=request_headers(assertion),
        json={
            "filename": uploaded_file.name,
            "content_type": content_type,
            "size_bytes": uploaded_file.size,
        },
        timeout=(10, 30),
    )
    response.raise_for_status()
    signed = response.json()
    uploaded = requests.put(
        signed["url"],
        data=uploaded_file.getvalue(),
        headers={
            "Content-Type": content_type,
            "Content-Length": str(uploaded_file.size),
        },
        timeout=(10, 120),
    )
    uploaded.raise_for_status()
    return signed["gcs_uri"]


def extract_parts(payload) -> tuple[str, list[str]]:
    """Separate visible answers from tool status, ignoring private thought parts."""
    if isinstance(payload, str):
        return payload, []
    if not isinstance(payload, dict):
        return "", []
    error = payload.get("error_message") or payload.get("errorMessage")
    if error:
        raise RuntimeError("Agent request failed. Please retry.")
    text, actions = [], []
    for part in payload.get("content", {}).get("parts", []):
        if part.get("thought"):
            continue
        if "text" in part:
            text.append(part["text"])
        call = part.get("functionCall") or part.get("function_call")
        if call:
            actions.append(call.get("name", "Tool").replace("_", " "))
    return "".join(text), actions
