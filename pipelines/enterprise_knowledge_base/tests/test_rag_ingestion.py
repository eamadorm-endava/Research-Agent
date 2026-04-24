from unittest.mock import MagicMock, patch

import pytest

from pipelines.enterprise_knowledge_base.rag_ingestion import (
    GenerateEmbeddingsRequest,
    IngestDocumentRequest,
    RAGIngestion,
)


@pytest.fixture(autouse=True)
def mock_config():
    """Mock the RAG_CONFIG to avoid environment dependency."""
    with patch(
        "pipelines.enterprise_knowledge_base.rag_ingestion.pipeline.RAG_CONFIG"
    ) as mock:
        mock.PROJECT_ID = "test-project"
        mock.BQ_DATASET = "knowledge_base"
        mock.BQ_CHUNKS_TABLE = "documents_chunks"
        mock.BQ_METADATA_TABLE = "documents_metadata"
        mock.CHUNK_SIZE = 1000
        mock.CHUNK_OVERLAP = 100
        mock.GCS_INGESTED_PREFIX = "ingested/"
        mock.GCS_PROCESSED_PREFIX = "processed/"
        mock.RAG_STAGING_BUCKET = "test-staging-bucket"
        yield mock


@pytest.fixture
def mock_storage():
    with patch(
        "pipelines.enterprise_knowledge_base.rag_ingestion.pipeline.storage.Client"
    ) as mock:
        yield mock


@pytest.fixture
def mock_bq():
    with patch(
        "pipelines.enterprise_knowledge_base.rag_ingestion.pipeline.bigquery.Client"
    ) as mock:
        mock_client = mock.return_value
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = []
        mock_client.query.return_value = mock_query_job
        yield mock


@pytest.fixture
def mock_fitz():
    with patch(
        "pipelines.enterprise_knowledge_base.rag_ingestion.pipeline.fitz.open"
    ) as mock:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is a test document. " * 100
        mock_doc.__iter__.return_value = [mock_page]
        mock.return_value = mock_doc
        yield mock


def test_ingest_document_success(mock_storage, mock_bq, mock_fitz):
    service = RAGIngestion()
    request = IngestDocumentRequest(gcs_uri="gs://test-bucket/ingested/test.pdf")

    response = service.ingest_document(request)

    assert response.chunk_count > 0
    assert response.execution_status == "SUCCESS"
    assert response.processed_uri == "gs://test-bucket/ingested/test.pdf"

    # Verify BQ calls
    mock_bq_client = mock_bq.return_value
    mock_bq_client.load_table_from_json.assert_called_once()

    # Verify GCS calls (should be 2 copies: Domain -> Staging, Staging Ingested -> Staging Processed)
    mock_bucket = mock_storage.return_value.bucket.return_value
    assert mock_bucket.copy_blob.call_count == 2


def test_ingest_document_already_processed(mock_storage, mock_bq, mock_fitz):
    service = RAGIngestion()
    mock_bq_client = mock_bq.return_value
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [{"dummy": 1}]
    mock_bq_client.query.return_value = mock_query_job

    request = IngestDocumentRequest(gcs_uri="gs://test-bucket/ingested/test.pdf")
    response = service.ingest_document(request)

    assert response.chunk_count == 0
    assert response.execution_status == "SKIPPED_ALREADY_PROCESSED"
    assert response.processed_uri == "gs://test-bucket/ingested/test.pdf"


def test_generate_embeddings_success(mock_bq):
    service = RAGIngestion()
    request = GenerateEmbeddingsRequest(gcs_uri="gs://test-bucket/processed/test.pdf")

    response = service.generate_embeddings(request)

    assert response.success is True
    assert response.execution_status == "SUCCESS"

    mock_bq_client = mock_bq.return_value
    mock_bq_client.query.assert_called_once()
    args, kwargs = mock_bq_client.query.call_args
    query_str = args[0]

    assert (
        "UPDATE `test-project.knowledge_base.documents_chunks` AS target" in query_str
    )
    assert "MODEL `test-project.knowledge_base.multimodal_embedding_model`" in query_str


def test_generate_embeddings_failure(mock_bq):
    service = RAGIngestion()
    mock_bq_client = mock_bq.return_value
    mock_bq_client.query.side_effect = Exception("BQ Error")

    request = GenerateEmbeddingsRequest(gcs_uri="gs://test-bucket/processed/test.pdf")
    response = service.generate_embeddings(request)

    assert response.success is False
    assert "BQ Error" in response.execution_status
