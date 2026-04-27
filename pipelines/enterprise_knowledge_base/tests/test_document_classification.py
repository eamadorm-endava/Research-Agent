import pytest
from unittest.mock import patch
from pipelines.enterprise_knowledge_base import ClassificationPipeline
from pipelines.enterprise_knowledge_base.document_classification.gcs_service.schemas import (
    DocumentMetadata,
)
from pipelines.enterprise_knowledge_base.document_classification.gemini_service.schemas import (
    ContextualClassificationResponse,
)
from pipelines.enterprise_knowledge_base.document_classification.bq_service.schemas import (
    GetLatestVersionResponse,
)
from pipelines.enterprise_knowledge_base.document_classification.schemas import (
    IngestMetadataBQRequest,
    RunResponse,
)


@pytest.fixture
def mock_gcs():
    """Fixture providing a mock GCSService."""
    with patch(
        "pipelines.enterprise_knowledge_base.document_classification.pipeline.GCSService"
    ) as mock:
        yield mock.return_value


@pytest.fixture
def mock_dlp():
    """Fixture providing a mock DLPService."""
    with patch(
        "pipelines.enterprise_knowledge_base.document_classification.pipeline.DLPService"
    ) as mock:
        yield mock.return_value


@pytest.fixture
def mock_gemini():
    """Fixture providing a mock GeminiService."""
    with patch(
        "pipelines.enterprise_knowledge_base.document_classification.pipeline.GeminiService"
    ) as mock:
        yield mock.return_value


@pytest.fixture
def mock_bq():
    """Fixture providing a mock BQService."""
    with patch(
        "pipelines.enterprise_knowledge_base.document_classification.pipeline.BQService"
    ) as mock:
        yield mock.return_value


@pytest.fixture
def pipeline(mock_gcs, mock_dlp, mock_gemini, mock_bq):
    """Fixture returning a ClassificationPipeline initialized with mocks."""
    return ClassificationPipeline()


def test_get_blob_metadata_extracts_structured_metadata(pipeline, mock_gcs):
    """Verifies that _get_blob_metadata returns a DocumentMetadata object."""
    expected_meta = DocumentMetadata(
        filename="secret_doc.pdf",
        mime_type="application/pdf",
        proposed_domain="hr",
        trust_level="wip",
        project_name="project_apollo",
        uploader_email="user@example.com",
        creator_name="Jane User",
        ingested_at="2026-04-16T12:00:00Z",
    )
    mock_gcs.get_blob_metadata.return_value = expected_meta

    uri = "gs://landing-bucket/secret_doc.pdf"
    result = pipeline._get_blob_metadata(uri)

    mock_gcs.get_blob_metadata.assert_called_once_with(uri)
    assert isinstance(result, DocumentMetadata)
    assert result.filename == "secret_doc.pdf"
    assert result.mime_type == "application/pdf"
    assert result.creator_name == "Jane User"


def test_dlp_trigger_with_findings_returns_masked(pipeline, mock_dlp, mock_gcs):
    """Verifies dlp_trigger returns the masked URI and appropriate tier when findings exist."""
    mock_dlp.inspect_gcs_file.return_value = "job/456"
    mock_dlp.wait_for_job.return_value = ["GOVERNMENT_ID", "CREDIT_CARD_DATA"]

    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="dirty_doc.txt",
        mime_type="text/plain",
        proposed_domain="it",
        trust_level="wip",
        project_name="apollo",
        uploader_email="sys@bot",
        creator_name="Bot",
    )
    mock_gcs.download_blob_bytes.return_value = b"Sensitive Content Here"
    mock_dlp.mask_content.return_value = b"Masked Content Here"

    expected_masked_uri = "gs://landing-bucket/dirty_doc_masked.txt"
    mock_gcs.upload_blob_bytes.return_value = expected_masked_uri

    uri = "gs://landing-bucket/dirty_doc.txt"
    result = pipeline.dlp_trigger(uri)

    assert result.sanitized_gcs_uri == expected_masked_uri
    assert result.proposed_classification_tier == 5


def test_ingest_metadata_bq_versioning_first_upload(pipeline, mock_bq):
    """Verifies version 1 is assigned on the first upload of a document."""
    request = IngestMetadataBQRequest(
        final_original_uri="gs://kb-hr/hr-data/strictly-confidential/admin/record.pdf",
        final_sanitized_uri=None,
        llm_classification=ContextualClassificationResponse(
            final_classification_tier=5,
            confidence=0.99,
            final_domain="hr",
            file_description="Employee performance record.",
        ),
        blob_metadata=DocumentMetadata(
            filename="record.pdf",
            mime_type="application/pdf",
            proposed_domain="hr",
            trust_level="published",
            project_name="hr-data",
            uploader_email="admin@hr.com",
        ),
    )

    # Mock BQ to return no previous versions
    mock_bq.get_latest_version.return_value = GetLatestVersionResponse(
        current_version=0
    )

    pipeline.ingest_metadata_bq(request)

    # Capture record
    args, _ = mock_bq.insert_metadata.call_args
    record = args[0]

    assert record.version == 1
    assert record.latest is True
    assert record.classification_tier == "strictly-confidential"
    mock_bq.deprecate_old_versions.assert_not_called()


def test_ingest_metadata_bq_versioning_increment(pipeline, mock_bq):
    """Verifies version is incremented and old versions deprecated on re-upload."""
    request = IngestMetadataBQRequest(
        final_original_uri="gs://kb-hr/hr-data/confidential/admin/record.pdf",
        final_sanitized_uri=None,
        llm_classification=ContextualClassificationResponse(
            final_classification_tier=4,
            confidence=0.90,
            final_domain="hr",
            file_description="Updated record.",
        ),
        blob_metadata=DocumentMetadata(
            filename="record.pdf",
            mime_type="application/pdf",
            proposed_domain="hr",
            trust_level="published",
            project_name="hr-data",
            uploader_email="admin@hr.com",
        ),
    )

    # Mock BQ to return version 2 already exists
    mock_bq.get_latest_version.return_value = GetLatestVersionResponse(
        current_version=2
    )

    pipeline.ingest_metadata_bq(request)

    # Capture record
    args, _ = mock_bq.insert_metadata.call_args
    record = args[0]

    assert record.version == 3
    assert record.latest is True
    assert record.classification_tier == "confidential"
    mock_bq.deprecate_old_versions.assert_called_once()


def test_deterministic_doc_id_consistency(pipeline, mock_bq):
    """Verifies that the same natural key results in the same document_id."""
    request = IngestMetadataBQRequest(
        final_original_uri="gs://kb-it/public/proj/user/doc.txt",
        final_sanitized_uri=None,
        llm_classification=ContextualClassificationResponse(
            final_classification_tier=1,
            confidence=1.0,
            final_domain="it",
            file_description="Public doc.",
        ),
        blob_metadata=DocumentMetadata(
            filename="doc.txt",
            mime_type="text/plain",
            proposed_domain="it",
            trust_level="published",
            project_name="proj",
        ),
    )

    mock_bq.get_latest_version.return_value = GetLatestVersionResponse(
        current_version=0
    )

    pipeline.ingest_metadata_bq(request)
    args1, _ = mock_bq.insert_metadata.call_args
    id1 = args1[0].document_id

    # Reset mock and run again with same data
    mock_bq.insert_metadata.reset_mock()
    pipeline.ingest_metadata_bq(request)
    args2, _ = mock_bq.insert_metadata.call_args
    id2 = args2[0].document_id

    assert id1 == id2
    assert isinstance(id1, str)
    assert len(id1) > 0


def test_run_orchestrates_full_pipeline_successfully(
    pipeline, mock_gcs, mock_dlp, mock_gemini, mock_bq
):
    """Verifies that the run method executes all stages and returns the final status."""
    landing_uri = "gs://landing/doc.pdf"

    # 1. Mock Metadata
    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="doc.pdf",
        mime_type="application/pdf",
        project_name="p1",
        uploader_email="u1@e.com",
        proposed_domain="it",
        trust_level="wip",
    )

    # 2. Mock DLP
    mock_dlp.inspect_gcs_file.return_value = "job1"
    mock_dlp.wait_for_job.return_value = []  # No findings
    mock_dlp.mask_content.return_value = b"masked"
    mock_gcs.upload_blob_bytes.return_value = "gs://landing/doc_masked.pdf"

    # 3. Mock Gemini
    mock_gemini.classify_document.return_value = ContextualClassificationResponse(
        final_classification_tier=1,
        confidence=1.0,
        final_domain="it",
        file_description="desc",
    )

    # 4. Mock Routing
    mock_gcs.copy_blob.return_value = True

    # 5. Mock BQ
    mock_bq.get_latest_version.return_value = GetLatestVersionResponse(
        current_version=0
    )
    mock_bq.insert_metadata.return_value = True

    result = pipeline.run(landing_uri)

    assert isinstance(result, RunResponse)
    assert result.final_domain == "it"
    assert result.final_security_tier == 1
    # Should return original destination URI because no masking occurred
    assert result.final_sanitized_uri == "gs://kb-it/p1/public/u1/doc.pdf"

    # Verify sequence
    mock_gcs.get_blob_metadata.assert_called()
    mock_dlp.inspect_gcs_file.assert_called_with(landing_uri)
    mock_gemini.classify_document.assert_called()
    mock_gcs.copy_blob.assert_called()
    mock_bq.insert_metadata.assert_called()


def test_run_performs_cleanup_on_failure(pipeline, mock_gcs, mock_dlp, mock_gemini):
    """Verifies that intermediate masked files are deleted if the pipeline fails."""
    landing_uri = "gs://landing/doc.pdf"
    masked_uri = "gs://landing/doc_masked.pdf"

    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="doc.txt",
        mime_type="text/plain",
        proposed_domain="hr",
        trust_level="published",
    )
    mock_dlp.inspect_gcs_file.return_value = "job1"
    mock_dlp.wait_for_job.return_value = ["US_SOCIAL_SECURITY_NUMBER"]  # Findings found
    mock_gcs.download_blob_bytes.return_value = b"bytes"
    mock_dlp.mask_content.return_value = b"masked"
    mock_gcs.upload_blob_bytes.return_value = masked_uri

    # Fail at Gemini
    mock_gemini.classify_document.side_effect = Exception("Gemini Down")

    with pytest.raises(Exception, match="Gemini Down"):
        pipeline.run(landing_uri)

    # Verify cleanup
    mock_gcs.delete_blob.assert_any_call(masked_uri)

    # Verify original was NOT deleted (since failure happened before routing)
    # Actually file_routing deletes it, but we failed before that.
    # We should check that delete_blob was NOT called for landing_uri.
    # Note: delete_blob might be called for masked_uri.

    calls = [call.args[0] for call in mock_gcs.delete_blob.call_args_list]
    assert landing_uri not in calls


def test_run_returns_masked_uri_when_sanitized(
    pipeline, mock_gcs, mock_dlp, mock_gemini, mock_bq
):
    """Verifies that the run method returns the masked URI if it exists."""
    landing_uri = "gs://landing/secret.txt"
    masked_landing_uri = "gs://landing/secret_masked.txt"

    # 1. Mock Metadata
    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="secret.txt",
        mime_type="text/plain",
        project_name="top-secret",
        uploader_email="admin@gov.com",
        proposed_domain="executives",
        trust_level="archived",
    )

    # 2. Mock DLP (Findings found)
    mock_dlp.inspect_gcs_file.return_value = "job-secret"
    mock_dlp.wait_for_job.return_value = ["US_SOCIAL_SECURITY_NUMBER"]
    mock_gcs.download_blob_bytes.return_value = b"raw pdf content"
    mock_dlp.mask_image_content.return_value = b"masked image"
    mock_gcs.upload_blob_bytes.return_value = masked_landing_uri

    # 3. Mock Gemini
    mock_gemini.classify_document.return_value = ContextualClassificationResponse(
        final_classification_tier=5,
        confidence=0.95,
        final_domain="executives",
        file_description="Secret doc.",
    )

    # 4. Mock Routing
    mock_gcs.copy_blob.return_value = True

    # 5. Mock BQ
    mock_bq.get_latest_version.return_value = GetLatestVersionResponse(
        current_version=1
    )
    mock_bq.insert_metadata.return_value = True

    result = pipeline.run(landing_uri)

    assert result.final_domain == "executives"
    assert result.final_security_tier == 5
    # Should return the final destination of the MASKED file
    assert (
        result.final_sanitized_uri
        == "gs://kb-executives/top-secret/strictly-confidential/admin/secret_masked.txt"
    )
