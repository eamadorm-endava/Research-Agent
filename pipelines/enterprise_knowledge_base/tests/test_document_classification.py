import pytest
from unittest.mock import patch
from pipelines.enterprise_knowledge_base import ClassificationPipeline
from pipelines.enterprise_knowledge_base.document_classification.schemas import (
    DocumentMetadata,
    DLPTriggerResponse,
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
def pipeline(mock_gcs, mock_dlp):
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
