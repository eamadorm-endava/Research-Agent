import sys
from loguru import logger

from .config import EKB_CONFIG
from .document_classification import ClassificationPipeline
from .document_classification.config import CLASSIFICATION_CONFIG
from .rag_ingestion import (
    IngestDocumentRequest,
    RAGIngestion,
)
from .schemas import OrchestratorRunRequest, PipelineResult


class KBIngestionPipeline:
    """Orchestrates the ingestion, classification, and vectorization of documents.

    This class serves as the central entry point for the EKB pipeline, coordinating
    the sequential execution of security classification and semantic indexing.
    """

    def __init__(self) -> None:
        """Initializes the orchestrator with required sub-services."""
        self.project_id = EKB_CONFIG.PROJECT_ID
        self.classification_pipeline = ClassificationPipeline()
        self.rag_pipeline = RAGIngestion()

    def run(self, request: OrchestratorRunRequest) -> PipelineResult:
        """Orchestrates the entire ingestion process end-to-end.

        Args:
            request: OrchestratorRunRequest -> The request containing the landing URI.

        Returns:
            PipelineResult -> Results of the pipeline execution.
        """
        logger.info(f"Triggering KB Ingestion Pipeline for: {request.gcs_uri}")

        logger.info("Step 1: Running Document Classification...")
        class_resp = self.classification_pipeline.run(request.gcs_uri)
        logger.info(f"Classification complete. Domain: {class_resp.final_domain}")

        logger.info(
            f"Step 2: Running RAG Ingestion for {class_resp.final_original_uri}..."
        )
        ingest_req = IngestDocumentRequest(
            gcs_uri=class_resp.final_original_uri,
            original_uri=class_resp.final_original_uri,
        )
        ingest_resp = self.rag_pipeline.run(ingest_req)

        if "SUCCESS" in ingest_resp.execution_status:
            logger.success(
                f"Pipeline finished successfully. Chunks: {ingest_resp.chunk_count}"
            )
        else:
            logger.warning(
                f"Pipeline finished with status: {ingest_resp.execution_status}"
            )

        tier_label = CLASSIFICATION_CONFIG.TIER_TO_LABEL.get(
            class_resp.final_security_tier, "unknown"
        )

        return PipelineResult(
            gcs_uri=class_resp.final_original_uri,
            chunks_generated=ingest_resp.chunk_count,
            final_domain=class_resp.final_domain,
            security_tier=tier_label,
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: uv run python -m pipelines.enterprise_knowledge_base.app.orchestrator <gcs_uri>"
        )
        sys.exit(1)

    input_uri = sys.argv[1]

    pipeline = KBIngestionPipeline()
    run_req = OrchestratorRunRequest(gcs_uri=input_uri)
    response = pipeline.run(run_req)
    print(response.model_dump_json(indent=2))
