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
