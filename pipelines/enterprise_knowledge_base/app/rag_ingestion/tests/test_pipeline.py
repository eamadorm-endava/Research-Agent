import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from pipelines.enterprise_knowledge_base.app.rag_ingestion.pipeline import RAGIngestion
from pipelines.enterprise_knowledge_base.app.rag_ingestion.schemas import DocumentChunk


@pytest.fixture
def rag_svc():
    with (
        patch(
            "pipelines.enterprise_knowledge_base.app.rag_ingestion.pipeline.RAGIngestion.storage_client"
        ),
        patch(
            "pipelines.enterprise_knowledge_base.app.rag_ingestion.pipeline.RAGIngestion.bq_client"
        ),
    ):
        yield RAGIngestion()


def test_chunking_character_limit(rag_svc):
    """Verifies that chunks are strictly under the 1024 character limit."""
    long_text = "Word " * 500  # ~2500 characters

    chunks = rag_svc.text_splitter.split_text(long_text)

    for chunk in chunks:
        assert len(chunk) <= 1024
        assert len(chunk) <= rag_svc.text_splitter._chunk_size


def test_pure_content_query_generation(rag_svc):
    """Verifies that the embedding query vectorizes pure content without metadata joins."""
    request = MagicMock()
    request.gcs_uri = "gs://test/doc.pdf"
    request.expected_chunk_count = 0

    mock_job = MagicMock()
    mock_job.num_dml_affected_rows = 1
    rag_svc.bq_client.query.return_value = mock_job

    rag_svc.generate_embeddings(request)

    args, _ = rag_svc.bq_client.query.call_args_list[0]
    query = args[0]

    assert "ML.GENERATE_EMBEDDING" in query
    assert "chunk_data AS content" in query
    assert "LEFT JOIN" not in query
    assert "CONCAT" not in query
    assert "NORMALIZE(c.gcs_uri)" in query


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
            structural_metadata={"page": 1},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    ]

    rag_svc._stage_chunks_bq(chunks)

    assert rag_svc.bq_client.load_table_from_json.called
    assert not rag_svc.bq_client.insert_rows_json.called
