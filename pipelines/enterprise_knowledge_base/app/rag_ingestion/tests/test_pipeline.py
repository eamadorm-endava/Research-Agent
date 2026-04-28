import pytest
from unittest.mock import MagicMock, patch
from pipelines.enterprise_knowledge_base.app.rag_ingestion.pipeline import RAGIngestion
from pipelines.enterprise_knowledge_base.app.rag_ingestion.schemas import DocumentChunk


@pytest.fixture
def rag_svc():
    with patch("google.cloud.storage.Client"), patch("google.cloud.bigquery.Client"):
        return RAGIngestion()


def test_chunking_character_limit(rag_svc):
    """Verifies that chunks are strictly under the 1024 character limit."""
    # Create a long text
    long_text = "Word " * 500  # ~2500 characters

    chunks = rag_svc.text_splitter.split_text(long_text)

    for chunk in chunks:
        assert len(chunk) <= 1024
        assert len(chunk) <= rag_svc.text_splitter._chunk_size


def test_pure_content_query_generation(rag_svc):
    """Verifies that the embedding query vectorizes pure content without metadata joins."""
    request = MagicMock()
    request.gcs_uri = "gs://test/doc.pdf"

    # We want to check the 'query' variable inside generate_embeddings
    # Since it's a local variable, we'll mock bq_client.query and check the call
    rag_svc.bq_client.query.return_value = MagicMock()

    try:
        rag_svc.generate_embeddings(request)
    except Exception:
        pass  # We only care about the call

    args, kwargs = rag_svc.bq_client.query.call_args
    query = args[0]

    # Assertions for Pure Content strategy
    assert "ML.GENERATE_EMBEDDING" in query
    assert "chunk_data AS content" in query
    assert "LEFT JOIN" not in query  # No metadata join
    assert "CONCAT" not in query  # No metadata injection
    assert "NORMALIZE(c.gcs_uri)" in query  # URI safety


def test_load_job_usage(rag_svc):
    """Verifies that Load Jobs are used instead of streaming inserts."""
    chunks = [
        DocumentChunk(
            chunk_id="1",
            document_id="doc1",
            chunk_data="data",
            gcs_uri="uri",
            filename="file",
            page_number=1,
        )
    ]

    rag_svc.bq_client.load_table_from_json = MagicMock()

    rag_svc._stage_chunks_bq(chunks)

    assert rag_svc.bq_client.load_table_from_json.called
    assert (
        not hasattr(rag_svc.bq_client, "insert_rows_json")
        or not rag_svc.bq_client.insert_rows_json.called
    )
