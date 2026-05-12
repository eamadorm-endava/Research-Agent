import pytest
from unittest.mock import MagicMock, patch
from pipelines.enterprise_knowledge_base.app.orchestrator import KBIngestionPipeline
from pipelines.enterprise_knowledge_base.app.schemas import (
    OrchestratorRunRequest,
    PipelineResult,
)


def test_orchestrator_run_returns_pipeline_result():
    """
    Regression test: Ensure the orchestrator returns PipelineResult, not OrchestratorRunResponse.
    This prevents validation errors in the background task that manages job status updates.
    """
    with (
        patch(
            "pipelines.enterprise_knowledge_base.app.orchestrator.ClassificationPipeline"
        ),
        patch("pipelines.enterprise_knowledge_base.app.orchestrator.RAGIngestion"),
    ):
        pipeline = KBIngestionPipeline()

        # Mock internal pipeline responses
        mock_class_resp = MagicMock()
        mock_class_resp.final_original_uri = "gs://kb-it/project/file.pdf"
        mock_class_resp.final_domain = "it"
        mock_class_resp.final_security_tier = 1  # Tier 1 -> public
        pipeline.classification_pipeline.run.return_value = mock_class_resp

        mock_rag_resp = MagicMock()
        mock_rag_resp.chunk_count = 42
        mock_rag_resp.execution_status = "SUCCESS"
        pipeline.rag_pipeline.run.return_value = mock_rag_resp

        request = OrchestratorRunRequest(gcs_uri="gs://landing/file.pdf")
        result = pipeline.run(request)

        # Validation
        assert isinstance(result, PipelineResult), (
            "Orchestrator must return PipelineResult"
        )
        assert result.gcs_uri == "gs://kb-it/project/file.pdf"
        assert result.chunks_generated == 42
        assert result.final_domain == "it"
        assert result.security_tier == "public"

        # Ensure it does not contain the OrchestratorRunResponse fields which would fail validation
        # if they were required but missing (the root cause of the bug).
        assert not hasattr(result, "job_id")
        assert not hasattr(result, "status")


def test_orchestrator_cleanup_called_after_rag_success():
    """Regression: cleanup_landing_zone must be called only after RAG succeeds."""
    with (
        patch(
            "pipelines.enterprise_knowledge_base.app.orchestrator.ClassificationPipeline"
        ),
        patch("pipelines.enterprise_knowledge_base.app.orchestrator.RAGIngestion"),
    ):
        pipeline = KBIngestionPipeline()

        mock_class_resp = MagicMock()
        mock_class_resp.final_original_uri = "gs://kb-it/project/file.pdf"
        mock_class_resp.final_domain = "it"
        mock_class_resp.final_security_tier = 1
        mock_class_resp.sanitized_landing_uri = "gs://landing/file_masked.pdf"
        pipeline.classification_pipeline.run.return_value = mock_class_resp

        mock_rag_resp = MagicMock()
        mock_rag_resp.chunk_count = 10
        mock_rag_resp.execution_status = "SUCCESS"
        pipeline.rag_pipeline.run.return_value = mock_rag_resp

        request = OrchestratorRunRequest(gcs_uri="gs://landing/file.pdf")
        pipeline.run(request)

        pipeline.classification_pipeline.cleanup_landing_zone.assert_called_once_with(
            "gs://landing/file.pdf", "gs://landing/file_masked.pdf"
        )


def test_orchestrator_cleanup_not_called_on_rag_failure():
    """Regression: cleanup_landing_zone must NOT be called if RAG ingestion fails,
    so the original file remains in the landing zone for a clean retry."""
    with (
        patch(
            "pipelines.enterprise_knowledge_base.app.orchestrator.ClassificationPipeline"
        ),
        patch("pipelines.enterprise_knowledge_base.app.orchestrator.RAGIngestion"),
    ):
        pipeline = KBIngestionPipeline()

        mock_class_resp = MagicMock()
        mock_class_resp.final_original_uri = "gs://kb-it/project/file.pdf"
        mock_class_resp.final_domain = "it"
        mock_class_resp.final_security_tier = 1
        mock_class_resp.sanitized_landing_uri = None
        pipeline.classification_pipeline.run.return_value = mock_class_resp

        pipeline.rag_pipeline.run.side_effect = Exception("BQ 429 rateLimitExceeded")

        request = OrchestratorRunRequest(gcs_uri="gs://landing/file.pdf")
        with pytest.raises(Exception, match="BQ 429 rateLimitExceeded"):
            pipeline.run(request)

        pipeline.classification_pipeline.cleanup_landing_zone.assert_not_called()
