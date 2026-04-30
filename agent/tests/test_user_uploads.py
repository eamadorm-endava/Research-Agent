import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from google.genai import types

from agent.core_agent.plugins.user_uploads import GeminiEnterpriseFileIngestionPlugin

pytestmark = pytest.mark.asyncio


# ─── JWT helper ───────────────────────────────────────────────────────────────


def _make_jwt_token(email: str) -> str:
    """Build a minimal JWT-formatted token string carrying an email claim for testing."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(json.dumps({"email": email}).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}.fakesignature"


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _make_inline_part(
    data: bytes = b"fake-bytes",
    mime_type: str = "image/png",
    display_name: str | None = None,
) -> types.Part:
    blob = MagicMock()
    blob.data = data
    blob.mime_type = mime_type
    blob.display_name = display_name
    part = MagicMock(spec=types.Part)
    part.inline_data = blob
    return part


def _make_text_part(text: str = "Hello") -> types.Part:
    part = MagicMock(spec=types.Part)
    part.inline_data = None
    part.text = text
    return part


def _make_artifact_version(
    canonical_uri: str | None = "gs://bucket/file.png",
) -> MagicMock:
    version = MagicMock()
    version.canonical_uri = canonical_uri
    version.mime_type = "image/png"
    return version


def _make_invocation_context(
    artifact_service: MagicMock | None = None,
    save_artifact_version: int = 0,
    artifact_version: MagicMock | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.invocation_id = "inv-123"
    ctx.app_name = "test-app"
    ctx.user_id = "user-1"
    ctx.session = MagicMock()
    ctx.session.id = "session-1"

    if artifact_service is None:
        svc = AsyncMock()
        svc.save_artifact = AsyncMock(return_value=save_artifact_version)
        svc.get_artifact_version = AsyncMock(
            return_value=artifact_version or _make_artifact_version()
        )
        ctx.artifact_service = svc
    else:
        ctx.artifact_service = artifact_service

    return ctx


def _make_user_message(parts: list) -> types.Content:
    msg = MagicMock(spec=types.Content)
    msg.role = "user"
    msg.parts = parts
    return msg


# ─── Happy Path ───────────────────────────────────────────────────────────────


async def test_inline_file_with_display_name_is_saved_and_replaced():
    """Should save a named inline file to GCS and replace it with a text placeholder + file_data Part."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(
        display_name="report.pdf", mime_type="application/pdf"
    )
    ctx = _make_invocation_context()
    msg = _make_user_message([inline_part])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert result.role == "user"
    ctx.artifact_service.save_artifact.assert_called_once()
    call_kwargs = ctx.artifact_service.save_artifact.call_args.kwargs
    assert call_kwargs["filename"] == "report.pdf"
    assert call_kwargs["app_name"] == "test-app"
    assert call_kwargs["user_id"] == "user-1"
    assert call_kwargs["session_id"] == "session-1"


async def test_inline_file_without_display_name_uses_fallback_filename():
    """Should derive a fallback filename from invocation_id when display_name is absent."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name=None)
    ctx = _make_invocation_context()
    msg = _make_user_message([inline_part])

    await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)

    call_kwargs = ctx.artifact_service.save_artifact.call_args.kwargs
    assert "inv-123" in call_kwargs["filename"]


async def test_result_includes_text_placeholder_and_gcs_file_data_part():
    """Should return both a text placeholder Part and a GCS file_data Part for each inline file."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="photo.png", mime_type="image/png")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version("gs://bucket/photo.png")
    )
    msg = _make_user_message([inline_part])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert len(result.parts) == 2
    placeholder = result.parts[0]
    file_ref = result.parts[1]
    assert '[Uploaded Artifact: "photo.png"]' in placeholder.text
    assert file_ref.file_data.file_uri == "gs://bucket/photo.png"
    assert file_ref.file_data.mime_type == "image/png"


async def test_mixed_message_preserves_text_parts_and_replaces_inline_parts():
    """Should keep text parts unchanged and replace only inline-data parts."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    text_part = _make_text_part("Analyze this file:")
    inline_part = _make_inline_part(display_name="data.csv", mime_type="text/csv")
    ctx = _make_invocation_context()
    msg = _make_user_message([text_part, inline_part])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert result.parts[0] is text_part
    assert len(result.parts) == 3  # text + placeholder + file_data


# ─── Edge Cases ───────────────────────────────────────────────────────────────


async def test_returns_none_when_no_artifact_service_available():
    """Should return None (pass through) when no artifact service is configured."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()
    ctx.artifact_service = None
    msg = _make_user_message([_make_inline_part()])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is None


async def test_returns_none_when_message_has_no_parts():
    """Should return None when the user message contains no parts."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()
    msg = _make_user_message(parts=[])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is None


async def test_returns_none_when_message_has_no_inline_data():
    """Should return None (unmodified pass-through) when no inline parts are present."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()
    msg = _make_user_message([_make_text_part("Just text")])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is None
    ctx.artifact_service.save_artifact.assert_not_called()


async def test_skips_gcs_file_data_part_when_canonical_uri_is_none():
    """Should return only the text placeholder when the artifact has no canonical URI."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="file.png")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version(canonical_uri=None)
    )
    msg = _make_user_message([inline_part])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert len(result.parts) == 1
    assert "[Uploaded Artifact:" in result.parts[0].text


async def test_skips_gcs_file_data_part_when_uri_is_not_gcs_scheme():
    """Should return only the text placeholder when the canonical URI is not a gs:// URI."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="file.png")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version(
            "https://storage.googleapis.com/bucket/file.png"
        )
    )
    msg = _make_user_message([inline_part])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert len(result.parts) == 1


async def test_multiple_inline_files_are_all_processed():
    """Should process every inline file in the message independently."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    part_a = _make_inline_part(display_name="a.png", mime_type="image/png")
    part_b = _make_inline_part(display_name="b.pdf", mime_type="application/pdf")

    svc = AsyncMock()
    svc.save_artifact = AsyncMock(side_effect=[0, 1])
    v_a = _make_artifact_version("gs://bucket/a.png")
    v_b = _make_artifact_version("gs://bucket/b.pdf")
    svc.get_artifact_version = AsyncMock(side_effect=[v_a, v_b])
    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message([part_a, part_b])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert svc.save_artifact.call_count == 2
    assert len(result.parts) == 4  # placeholder + file_data for each


# ─── Failure Modes ────────────────────────────────────────────────────────────


async def test_falls_back_to_original_part_when_save_artifact_raises():
    """Should keep the original inline part when save_artifact raises, to avoid data loss."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="file.png")
    svc = AsyncMock()
    svc.save_artifact = AsyncMock(side_effect=RuntimeError("GCS write failure"))
    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message([inline_part])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert result.parts[0] is inline_part


async def test_skips_gcs_part_when_get_artifact_version_raises():
    """Should return only the text placeholder when get_artifact_version raises unexpectedly."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="file.png")
    svc = AsyncMock()
    svc.save_artifact = AsyncMock(return_value=0)
    svc.get_artifact_version = AsyncMock(side_effect=RuntimeError("GCS read failure"))
    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message([inline_part])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert len(result.parts) == 1
    assert "[Uploaded Artifact:" in result.parts[0].text


async def test_one_failed_part_does_not_prevent_other_parts_from_processing():
    """Should process remaining parts even when one inline part fails to save."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    failing_part = _make_inline_part(display_name="bad.png")
    good_part = _make_inline_part(display_name="good.png")

    svc = AsyncMock()
    svc.save_artifact = AsyncMock(side_effect=[RuntimeError("GCS error"), 0])
    svc.get_artifact_version = AsyncMock(
        return_value=_make_artifact_version("gs://bucket/good.png")
    )
    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message([failing_part, good_part])

    with patch("agent.core_agent.plugins.user_uploads.storage.Client"):
        result = await plugin.on_user_message_callback(
            invocation_context=ctx, user_message=msg
        )

    assert result is not None
    assert result.parts[0] is failing_part
    assert len(result.parts) == 3  # original failing + placeholder + file_data for good


# ─── GE Text-Extraction Format ───────────────────────────────────────────────


def _make_ge_text_part(filename: str, content: str) -> list:
    """Build the 2-part GE text-extraction structure for a single file."""
    start = MagicMock(spec=types.Part)
    start.inline_data = None
    start.file_data = None
    start.text = f"\n<start_of_user_uploaded_file: {filename}>\n{content}\n"

    end = MagicMock(spec=types.Part)
    end.inline_data = None
    end.file_data = None
    end.text = f"<end_of_user_uploaded_file: {filename}>\n"

    return [start, end]


async def test_ge_text_extracted_file_is_saved_and_placeholder_returned():
    """Should save a GE text-extracted file as a .txt artifact and replace the tag block."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    text_part = _make_text_part("Summarize this")
    file_parts = _make_ge_text_part("report.pdf", "This is the extracted PDF text.")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version("gs://bucket/report.pdf.txt")
    )
    msg = _make_user_message([text_part] + file_parts)

    with patch("agent.core_agent.plugins.user_uploads.storage.Client"):
        result = await plugin.on_user_message_callback(
            invocation_context=ctx, user_message=msg
        )

    assert result is not None
    ctx.artifact_service.save_artifact.assert_called_once()
    call_kwargs = ctx.artifact_service.save_artifact.call_args.kwargs
    assert call_kwargs["filename"] == "report.pdf.txt"
    assert call_kwargs["user_id"] == "user-1"
    placeholder_texts = [p.text for p in result.parts if hasattr(p, "text") and p.text]
    assert any('[Uploaded Artifact: "report.pdf"]' in t for t in placeholder_texts)


async def test_ge_text_extracted_file_preserves_non_file_text():
    """Should keep the user's prompt text and strip only the GE file tag block."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    text_part = _make_text_part("Summarize this")
    file_parts = _make_ge_text_part("doc.pdf", "PDF content here.")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version("gs://bucket/doc.pdf.txt")
    )
    msg = _make_user_message([text_part] + file_parts)

    with patch("agent.core_agent.plugins.user_uploads.storage.Client"):
        result = await plugin.on_user_message_callback(
            invocation_context=ctx, user_message=msg
        )

    assert result is not None
    all_text = " ".join(p.text for p in result.parts if getattr(p, "text", None))
    assert "Summarize this" in all_text


async def test_multiple_ge_text_extracted_files_all_saved():
    """Should save every GE text-extracted file found across all parts."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    parts_a = _make_ge_text_part("a.pdf", "Content of A.")
    parts_b = _make_ge_text_part("b.pdf", "Content of B.")

    svc = AsyncMock()
    svc.save_artifact = AsyncMock(side_effect=[0, 1])
    v_a = _make_artifact_version("gs://bucket/a.pdf.txt")
    v_b = _make_artifact_version("gs://bucket/b.pdf.txt")
    svc.get_artifact_version = AsyncMock(side_effect=[v_a, v_b])
    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message(parts_a + parts_b)

    with patch("agent.core_agent.plugins.user_uploads.storage.Client"):
        result = await plugin.on_user_message_callback(
            invocation_context=ctx, user_message=msg
        )

    assert result is not None
    assert svc.save_artifact.call_count == 2


async def test_ge_text_extracted_file_falls_back_on_save_failure():
    """Should restore the original tag block when artifact save fails."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    file_parts = _make_ge_text_part("fail.pdf", "Some content.")
    svc = AsyncMock()
    svc.save_artifact = AsyncMock(side_effect=RuntimeError("GCS write error"))
    ctx = _make_invocation_context(artifact_service=svc)
    msg = _make_user_message(file_parts)

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is not None
    assert any(
        "start_of_user_uploaded_file" in (getattr(p, "text", "") or "")
        for p in result.parts
    )


async def test_returns_none_when_no_inline_data_and_no_ge_text_blocks():
    """Should return None when neither inline_data nor GE text blocks are present."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    ctx = _make_invocation_context()
    msg = _make_user_message([_make_text_part("Just a question, no file")])

    result = await plugin.on_user_message_callback(
        invocation_context=ctx, user_message=msg
    )

    assert result is None


# ─── ACL Grant ────────────────────────────────────────────────────────────────


async def test_grants_uploader_objectadmin_via_iam_on_successful_upload():
    """Should grant roles/storage.objectAdmin via conditional IAM binding on upload."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(
        display_name="report.pdf", mime_type="application/pdf"
    )
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version("gs://landing-zone/report.pdf")
    )
    ctx.user_id = "uploader@example.com"
    msg = _make_user_message([inline_part])

    mock_policy = MagicMock()
    mock_policy.bindings = []

    with patch("agent.core_agent.storage.service.storage.Client") as mock_client:
        mock_blob = MagicMock()
        mock_blob.metadata = {}
        mock_bucket = MagicMock()
        mock_bucket.get_blob.return_value = mock_blob
        mock_bucket.get_iam_policy.return_value = mock_policy
        mock_client.return_value.bucket.return_value = mock_bucket

        await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)

    mock_client.return_value.bucket.assert_called_once_with("landing-zone")
    mock_bucket.get_blob.assert_called_once_with("report.pdf")
    mock_bucket.get_iam_policy.assert_called_once_with(requested_policy_version=3)
    mock_bucket.set_iam_policy.assert_called_once_with(mock_policy)
    assert len(mock_policy.bindings) == 1
    binding = mock_policy.bindings[0]
    assert binding["role"] == "roles/storage.objectAdmin"
    assert "user:uploader@example.com" in binding["members"]
    assert binding["condition"]["expression"] == (
        'resource.name.startsWith("projects/_/buckets/landing-zone/objects/test-app/uploader@example.com/")'
    )
    assert mock_blob.metadata["uploader"] == "uploader@example.com"
    mock_blob.patch.assert_called_once()


async def test_acl_grant_failure_does_not_block_upload():
    """Should complete the upload and return parts even when the IAM grant fails."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="file.png")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version("gs://landing-zone/file.png")
    )
    msg = _make_user_message([inline_part])

    with patch("agent.core_agent.storage.service.storage.Client") as mock_client:
        mock_blob = MagicMock()
        mock_blob.metadata = {}
        mock_bucket = MagicMock()
        mock_bucket.get_blob.return_value = mock_blob
        mock_bucket.get_iam_policy.side_effect = RuntimeError("IAM error")
        mock_client.return_value.bucket.return_value = mock_bucket

        result = await plugin.on_user_message_callback(
            invocation_context=ctx, user_message=msg
        )

    assert result is not None
    assert len(result.parts) == 2  # placeholder + file_data still returned


async def test_acl_not_attempted_when_no_gcs_uri():
    """Should skip ACL grant entirely when the canonical URI is unavailable."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="file.png")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version(canonical_uri=None)
    )
    msg = _make_user_message([inline_part])

    with patch("agent.core_agent.storage.service.storage.Client") as mock_client:
        await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)

    mock_client.assert_not_called()


# ─── Identity Verification ───────────────────────────────────────────────────


async def test_grants_iam_objectadmin_to_user_id_from_context():
    """Should grant roles/storage.objectAdmin to the user_id provided in the invocation context."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="report.pdf")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version("gs://landing-zone/report.pdf")
    )
    ctx.user_id = "emmanuel.amador@endava.com"
    msg = _make_user_message([inline_part])

    mock_policy = MagicMock()
    mock_policy.bindings = []

    with patch("agent.core_agent.storage.service.storage.Client") as mock_client:
        mock_blob = MagicMock()
        mock_blob.metadata = {}
        mock_bucket = MagicMock()
        mock_bucket.get_blob.return_value = mock_blob
        mock_bucket.get_iam_policy.return_value = mock_policy
        mock_client.return_value.bucket.return_value = mock_bucket

        await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)

    mock_bucket.get_iam_policy.assert_called_once_with(requested_policy_version=3)
    assert len(mock_policy.bindings) == 1
    assert "user:emmanuel.amador@endava.com" in mock_policy.bindings[0]["members"]
    assert "startsWith" in mock_policy.bindings[0]["condition"]["expression"]


async def test_skips_duplicate_iam_binding_on_repeated_upload():
    """Should not add a duplicate IAM binding when an identical one already exists."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    inline_part = _make_inline_part(display_name="report.pdf")
    ctx = _make_invocation_context(
        artifact_version=_make_artifact_version("gs://landing-zone/report.pdf")
    )
    ctx.user_id = "user@example.com"
    msg = _make_user_message([inline_part])

    condition_expr = 'resource.name.startsWith("projects/_/buckets/landing-zone/objects/test-app/user@example.com/")'
    existing_binding = {
        "role": "roles/storage.objectAdmin",
        "members": {"user:user@example.com"},
        "condition": {"title": "uploader-object-access", "expression": condition_expr},
    }
    mock_policy = MagicMock()
    mock_policy.bindings = [existing_binding]

    with patch("agent.core_agent.storage.service.storage.Client") as mock_client:
        mock_blob = MagicMock()
        mock_blob.metadata = {}
        mock_bucket = MagicMock()
        mock_bucket.get_blob.return_value = mock_blob
        mock_bucket.get_iam_policy.return_value = mock_policy
        mock_client.return_value.bucket.return_value = mock_bucket

        await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)

    mock_bucket.set_iam_policy.assert_not_called()
    assert len(mock_policy.bindings) == 1


async def test_grants_iam_objectadmin_on_existing_gcs_references():
    """Should scan message parts for existing GCS URIs and grant IAM objectAdmin to the context user_id."""
    plugin = GeminiEnterpriseFileIngestionPlugin()
    gcs_uri = "gs://pre-uploaded/file.pdf"
    gcs_part = MagicMock(spec=types.Part)
    gcs_part.inline_data = None
    gcs_part.file_data = types.FileData(file_uri=gcs_uri, mime_type="application/pdf")

    ctx = _make_invocation_context()
    ctx.user_id = "emmanuel.amador@endava.com"
    msg = _make_user_message([gcs_part])

    mock_policy = MagicMock()
    mock_policy.bindings = []

    with patch("agent.core_agent.storage.service.storage.Client") as mock_client:
        mock_blob = MagicMock()
        mock_blob.metadata = {}
        mock_bucket = MagicMock()
        mock_bucket.get_blob.return_value = mock_blob
        mock_bucket.get_iam_policy.return_value = mock_policy
        mock_client.return_value.bucket.return_value = mock_bucket

        await plugin.on_user_message_callback(invocation_context=ctx, user_message=msg)

    mock_client.return_value.bucket.assert_called_once_with("pre-uploaded")
    mock_bucket.get_blob.assert_called_once_with("file.pdf")
    mock_bucket.get_iam_policy.assert_called_once_with(requested_policy_version=3)
    assert len(mock_policy.bindings) == 1
    assert "user:emmanuel.amador@endava.com" in mock_policy.bindings[0]["members"]
    assert "startsWith" in mock_policy.bindings[0]["condition"]["expression"]
