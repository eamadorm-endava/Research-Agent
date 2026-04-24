import json
from unittest.mock import MagicMock, patch
import pytest

from pipelines.enterprise_knowledge_base.rag_ingestion import RAGIngestion

@pytest.fixture
def mock_storage():
    with patch("pipelines.enterprise_knowledge_base.rag_ingestion.rag_ingestion.storage.Client") as mock:
        yield mock

@pytest.fixture
def mock_bq():
    with patch("pipelines.enterprise_knowledge_base.rag_ingestion.rag_ingestion.bigquery.Client") as mock:
        mock_client = mock.return_value
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = []
        mock_client.query.return_value = mock_query_job
        yield mock

@pytest.fixture
def mock_fitz():
    with patch("pipelines.enterprise_knowledge_base.rag_ingestion.rag_ingestion.fitz.open") as mock:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is a test document. " * 100
        mock_doc.__iter__.return_value = [mock_page]
        mock.return_value = mock_doc
        yield mock

def test_process_document(mock_storage, mock_bq, mock_fitz):
    ingestion = RAGIngestion(project_id="test-project")
    chunks = ingestion.process_document("gs://test-bucket/test.pdf")
    
    assert len(chunks) > 0
    first_chunk = chunks[0]
    
    expected_keys = {
        "chunk_id", "document_id", "chunk_data", "gcs_uri", "filename", 
        "structural_metadata", "page_number", "embedding", 
        "created_at", "vectorized_at"
    }
    assert set(first_chunk.keys()) == expected_keys
    assert first_chunk["gcs_uri"] == "gs://test-bucket/test.pdf"
    assert first_chunk["filename"] == "test.pdf"
    assert first_chunk["page_number"] == 1
    assert first_chunk["embedding"] == []
    assert first_chunk["vectorized_at"] is None

def test_process_document_already_processed(mock_storage, mock_bq, mock_fitz):
    ingestion = RAGIngestion(project_id="test-project")
    mock_bq_client = mock_bq.return_value
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [{"dummy": 1}]
    mock_bq_client.query.return_value = mock_query_job
    
    with pytest.raises(FileExistsError):
        ingestion.process_document("gs://test-bucket/test.pdf")

def test_stage_chunks_bq(mock_storage, mock_bq):
    ingestion = RAGIngestion(project_id="test-project")
    mock_bq_client = mock_bq.return_value
    mock_bq_client.insert_rows_json.return_value = []
    
    test_chunks = [{"chunk_id": "123", "chunk_data": "test"}]
    ingestion.stage_chunks_bq(test_chunks)
    
    mock_bq_client.insert_rows_json.assert_called_once_with(
        "test-project.knowledge_base.documents_chunks", 
        test_chunks
    )

def test_run_staging(mock_storage, mock_bq, mock_fitz):
    ingestion = RAGIngestion(project_id="test-project")
    mock_bq_client = mock_bq.return_value
    mock_bq_client.insert_rows_json.return_value = []
    
    mock_bucket = mock_storage.return_value.bucket.return_value
    
    count = ingestion.run_staging("gs://test-bucket/ingested/test.pdf")
    assert count > 0
    mock_bq_client.insert_rows_json.assert_called_once()
    mock_bucket.copy_blob.assert_called_once()

def test_move_blob_to_processed(mock_storage):
    ingestion = RAGIngestion(project_id="test-project")
    mock_bucket = mock_storage.return_value.bucket.return_value
    mock_blob = mock_bucket.blob.return_value
    
    result = ingestion.move_blob_to_processed("gs://test-bucket/ingested/test.pdf")
    
    assert result == "gs://test-bucket/processed/test.pdf"
    mock_bucket.copy_blob.assert_called_once_with(mock_blob, mock_bucket, "processed/test.pdf")
    mock_blob.delete.assert_called_once()

def test_move_blob_to_processed_no_ingested(mock_storage):
    ingestion = RAGIngestion(project_id="test-project")
    mock_bucket = mock_storage.return_value.bucket.return_value
    mock_blob = mock_bucket.blob.return_value
    
    result = ingestion.move_blob_to_processed("gs://test-bucket/other/test.pdf")
    
    assert result == "gs://test-bucket/other/test.pdf"
    mock_bucket.copy_blob.assert_not_called()
    mock_blob.delete.assert_not_called()

def test_generate_embeddings(mock_storage, mock_bq):
    ingestion = RAGIngestion(project_id="test-project")
    mock_bq_client = mock_bq.return_value
    mock_query_job = MagicMock()
    mock_bq_client.query.return_value = mock_query_job

    result = ingestion.generate_embeddings("gs://test-bucket/test.pdf")

    assert result is True
    mock_bq_client.query.assert_called_once()
    args, kwargs = mock_bq_client.query.call_args
    query_str = args[0]
    
    assert "UPDATE `test-project.knowledge_base.documents_chunks` AS target" in query_str
    assert "MODEL `test-project.knowledge_base.multimodal_embedding_model`" in query_str
    assert "LEFT JOIN `test-project.knowledge_base.documents_metadata` m" in query_str
    
    job_config = kwargs.get("job_config")
    assert job_config is not None
    assert len(job_config.query_parameters) == 1
    assert job_config.query_parameters[0].name == "gcs_uri"
    assert job_config.query_parameters[0].value == "gs://test-bucket/test.pdf"

def test_generate_embeddings_failure(mock_storage, mock_bq):
    ingestion = RAGIngestion(project_id="test-project")
    mock_bq_client = mock_bq.return_value
    mock_bq_client.query.side_effect = Exception("BQ Error")

    with pytest.raises(RuntimeError) as exc_info:
        ingestion.generate_embeddings("gs://test-bucket/test.pdf")

    assert "Failed to generate embeddings: BQ Error" in str(exc_info.value)
