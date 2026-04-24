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
        final_original_uri="gs://kb-hr/strictly-confidential/hr-data/admin/record.pdf",
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
        final_original_uri="gs://kb-hr/confidential/hr-data/admin/record.pdf",
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
