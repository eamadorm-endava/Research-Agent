import pytest
from unittest.mock import patch
from pipelines.enterprise_knowledge_base import ClassificationPipeline
from pipelines.enterprise_knowledge_base.document_classification.schemas import (
    DocumentMetadata,
    DLPTriggerResponse,
    ContextualClassificationResponse,
    FileRoutingRequest,
    MetadataBQRequest,
    BQMetadataRecord,
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


def test_get_blob_metadata_handles_missing_creator(pipeline, mock_gcs):
    """Verifies that _get_blob_metadata handles missing creator name correctly."""
    expected_meta = DocumentMetadata(
        filename="no_creator.txt",
        mime_type="text/plain",
        proposed_domain="it",
        trust_level="wip",
        project_name="test",
        uploader_email="user@test.com",
        creator_name=None,
        ingested_at=None,
    )
    mock_gcs.get_blob_metadata.return_value = expected_meta

    uri = "gs://landing-bucket/no_creator.txt"
    result = pipeline._get_blob_metadata(uri)

    assert result.creator_name is None


def test_dlp_trigger_clean_returns_original(pipeline, mock_dlp):
    """Verifies dlp_trigger returns unmasked URI and None tier when no findings."""
    mock_dlp.inspect_gcs_file.return_value = "job/123"
    mock_dlp.wait_for_job.return_value = []

    uri = "gs://landing-bucket/clean_doc.txt"
    result = pipeline.dlp_trigger(uri)

    assert isinstance(result, DLPTriggerResponse)
    assert result.sanitized_gcs_uri == uri
    assert result.proposed_classification_tier is None


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
        ingested_at=None,
    )
    mock_gcs.download_blob_bytes.return_value = b"Sensitive Content Here"
    mock_dlp.mask_content.return_value = b"Masked Content Here"

    expected_masked_uri = "gs://landing-bucket/dirty_doc_masked.txt"
    mock_gcs.upload_blob_bytes.return_value = expected_masked_uri

    uri = "gs://landing-bucket/dirty_doc.txt"
    result = pipeline.dlp_trigger(uri)

    mock_dlp.mask_content.assert_called_once_with(
        b"Sensitive Content Here", "text/plain", True
    )
    assert result.sanitized_gcs_uri == expected_masked_uri
    assert result.proposed_classification_tier == 5


def test_dlp_trigger_contextual_masking_rule(pipeline, mock_dlp, mock_gcs):
    """Verifies dlp_trigger returns masked URI if document is high-risk."""
    mock_dlp.inspect_gcs_file.return_value = "job/789"
    mock_dlp.wait_for_job.return_value = [
        "DOCUMENT_TYPE/FINANCE/INVOICE",
        "PERSON_NAME",
    ]

    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="invoice.txt",
        mime_type="text/plain",
        proposed_domain="it",
        trust_level="wip",
        project_name="apollo",
        uploader_email="sys@bot",
        creator_name="Bot",
        ingested_at=None,
    )
    mock_gcs.download_blob_bytes.return_value = b"Sensitive"
    mock_dlp.mask_content.return_value = b"Masked"
    mock_gcs.upload_blob_bytes.return_value = "gs://landing-bucket/invoice_masked.txt"

    uri = "gs://landing-bucket/invoice.txt"
    result = pipeline.dlp_trigger(uri)

    mock_dlp.mask_content.assert_called_once_with(b"Sensitive", "text/plain", True)
    assert result.proposed_classification_tier == 4


def test_dlp_trigger_general_pii_no_context_is_ignored(pipeline, mock_dlp):
    """Verifies dlp_trigger ignores standard PII when NOT sensitive."""
    mock_dlp.inspect_gcs_file.return_value = "job/999"
    mock_dlp.wait_for_job.return_value = ["PERSON_NAME", "EMAIL_ADDRESS", "DATE"]

    uri = "gs://landing-bucket/generic_sow.txt"
    result = pipeline.dlp_trigger(uri)

    assert result.sanitized_gcs_uri == uri
    assert result.proposed_classification_tier is None


def test_dlp_trigger_pdf_local_masking(pipeline, mock_dlp, mock_gcs, mocker):
    """Verifies dlp_trigger handles PDF by routing to native manipulation."""
    mock_dlp.inspect_gcs_file.return_value = "job/789"
    mock_dlp.wait_for_job.return_value = [
        "DOCUMENT_TYPE/FINANCE/INVOICE",
        "PERSON_NAME",
    ]

    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="invoice.pdf",
        mime_type="application/pdf",
        proposed_domain="it",
        trust_level="wip",
        project_name="apollo",
        uploader_email="sys@bot",
        creator_name="Bot",
        ingested_at=None,
    )

    mock_mask_pdf = mocker.patch.object(
        pipeline, "_mask_pdf_locally", return_value=b"PDF Bytes"
    )
    expected_masked_uri = "gs://landing-bucket/dir/invoice_masked.pdf"
    mock_gcs.upload_blob_bytes.return_value = expected_masked_uri

    uri = "gs://landing-bucket/dir/invoice.pdf"
    result = pipeline.dlp_trigger(uri)

    mock_mask_pdf.assert_called_once()
    assert result.proposed_classification_tier == 4


def test_dlp_trigger_tier_5_keyword_high_risk(pipeline, mock_dlp, mock_gcs):
    """Verifies that Tier 5 keywords trigger Tier 5 classification."""
    mock_dlp.inspect_gcs_file.return_value = "job/555"
    mock_dlp.wait_for_job.return_value = ["TIER_5_KEYWORDS"]

    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="sev.txt",
        mime_type="text/plain",
        proposed_domain="it",
        trust_level="wip",
        project_name="apollo",
        uploader_email="sys@bot",
        creator_name="Bot",
        ingested_at=None,
    )
    mock_gcs.download_blob_bytes.return_value = b"Severance"
    mock_dlp.mask_content.return_value = b"Masked"
    mock_gcs.upload_blob_bytes.return_value = "gs://landing-bucket/sev_masked.txt"

    uri = "gs://landing-bucket/sev.txt"
    result = pipeline.dlp_trigger(uri)

    assert result.proposed_classification_tier == 5


def test_dlp_trigger_new_infotypes_trigger_tier_5(pipeline, mock_dlp, mock_gcs):
    """Verifies that new sensitive InfoTypes (SSN, API Key) trigger Tier 5."""
    mock_dlp.inspect_gcs_file.return_value = "job/112"
    # Testing some of the newly added InfoTypes
    mock_dlp.wait_for_job.return_value = ["US_SOCIAL_SECURITY_NUMBER", "GCP_API_KEY"]

    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="secrets.txt",
        mime_type="text/plain",
        proposed_domain="it",
        trust_level="wip",
        project_name="top-secret",
        uploader_email="admin@corp.com",
        creator_name="Admin",
        ingested_at=None,
    )
    mock_gcs.download_blob_bytes.return_value = b"SSN: 000-00-0000, Key: AIza..."
    mock_dlp.mask_content.return_value = b"Masked"
    mock_gcs.upload_blob_bytes.return_value = "gs://landing-bucket/secrets_masked.txt"

    uri = "gs://landing-bucket/secrets.txt"
    result = pipeline.dlp_trigger(uri)

    assert result.proposed_classification_tier == 5


def test_contextual_classification_calls_gemini_with_metadata(
    pipeline, mock_gcs, mock_gemini
):
    """Verifies that contextual_classification correctly orchestrates the Gemini call."""
    mock_gcs.get_blob_metadata.return_value = DocumentMetadata(
        filename="strategy.pdf",
        mime_type="application/pdf",
        proposed_domain="it",
        trust_level="published",
    )
    expected_response = ContextualClassificationResponse(
        final_classification_tier=4,
        confidence=0.95,
        final_domain="it",
        file_description="A strategic document about infrastructure.",
    )
    mock_gemini.classify_document.return_value = expected_response

    uri = "gs://landing-bucket/strategy_masked.pdf"
    result = pipeline.contextual_classification(
        sanitized_url=uri,
        proposed_classification_tier=4,
        proposed_domain="it",
        trust_level="published",
    )

    mock_gemini.classify_document.assert_called_once_with(
        gcs_uri=uri,
        mime_type="application/pdf",
        proposed_tier=4,
        proposed_domain="it",
        trust_level="published",
    )
    assert result.final_classification_tier == 4
    assert result.confidence == 0.95
    assert result.final_domain == "it"


def test_file_routing_moves_and_cleans_files(pipeline, mock_gcs):
    """Verifies that file_routing copies files to domain buckets and cleans landing zone."""
    request = FileRoutingRequest(
        original_landing_uri="gs://landing/doc.pdf",
        sanitized_landing_uri="gs://landing/doc_masked.pdf",
        final_domain="finance",
        final_security_tier=4,
        project_name="audit-2026",
        uploader_email="accountant@corp.com",
    )

    # Mock tier mapping (Tier 4 -> confidential)
    expected_original_dst = "gs://kb-finance/confidential/audit-2026/accountant/doc.pdf"
    expected_masked_dst = (
        "gs://kb-finance/confidential/audit-2026/accountant/doc_masked.pdf"
    )

    result = pipeline.file_routing(request)

    # Verify copies
    mock_gcs.copy_blob.assert_any_call(
        request.original_landing_uri, expected_original_dst
    )
    mock_gcs.copy_blob.assert_any_call(
        request.sanitized_landing_uri, expected_masked_dst
    )

    # Verify cleanup
    mock_gcs.delete_blob.assert_any_call(request.original_landing_uri)
    mock_gcs.delete_blob.assert_any_call(request.sanitized_landing_uri)

    assert result.final_original_uri == expected_original_dst


def test_metadata_bq_inserts_correct_record(pipeline, mock_bq):
    """Verifies that metadata_bq formats the record correctly and calls BQService."""
    request = MetadataBQRequest(
        final_original_uri="gs://kb-hr/strictly-confidential/hr-data/admin/record.pdf",
        final_sanitized_uri="gs://kb-hr/strictly-confidential/hr-data/admin/record_masked.pdf",
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

    pipeline.metadata_bq(request)

    # Capture the call to bq.insert_metadata
    args, _ = mock_bq.insert_metadata.call_args
    record_model = args[0]

    assert isinstance(record_model, BQMetadataRecord)
    assert record_model.gcs_uri == request.final_original_uri
    assert record_model.classification_tier == 5
    assert record_model.domain == "hr"
    assert record_model.uploader_email == "admin@hr.com"
    assert record_model.is_latest is True
    assert record_model.document_id is not None
