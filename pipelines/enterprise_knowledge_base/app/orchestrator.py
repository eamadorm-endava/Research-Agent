import sys
from loguru import logger

from .document_classification import ClassificationPipeline
from .document_classification.config import EKB_CONFIG
from .rag_ingestion import (
    IngestDocumentRequest,
    RAGIngestion,
)
from .schemas import OrchestratorRunRequest, OrchestratorRunResponse


class KBIngestionPipeline:
    """Orchestrates the ingestion, classification, and vectorization of documents.

    This class serves as the central entry point for the EKB pipeline, coordinating
    the sequential execution of security classification and semantic indexing.
    """

    def __init__(self, project_id: str):
        """Initializes the orchestrator with required sub-services.

        Args:
            project_id: str -> The GCP Project ID for all operations.
        """
        self.project_id = project_id
        self.classification_pipeline = ClassificationPipeline()
        self.rag_pipeline = RAGIngestion()

    def run(self, request: OrchestratorRunRequest) -> OrchestratorRunResponse:
        """Orchestrates the entire ingestion process end-to-end.

        Args:
            request: OrchestratorRunRequest -> The request containing the landing URI.

        Returns:
            OrchestratorRunResponse -> Results of the pipeline execution.
        """
        logger.info(f"Triggering KB Ingestion Pipeline for: {request.gcs_uri}")

        # 1. Execute Classification Pipeline
        logger.info("Step 1: Running Document Classification...")
        class_resp = self.classification_pipeline.run(request.gcs_uri)
        logger.info(f"Classification complete. Domain: {class_resp.final_domain}")

        # 2. Execute end-to-end RAG pipeline
        logger.info(
            f"Step 2: Running RAG Ingestion for {class_resp.final_original_uri}..."
        )
        ingest_req = IngestDocumentRequest(
            gcs_uri=class_resp.final_original_uri,
            original_uri=class_resp.final_original_uri,
        )
        ingest_resp = self.rag_pipeline.run(ingest_req)

        if "SUCCESS" in ingest_resp.execution_status:
            logger.info(
                f"Pipeline finished successfully. Chunks: {ingest_resp.chunk_count}"
            )
        else:
            logger.warning(
                f"Pipeline finished with status: {ingest_resp.execution_status}"
            )

        tier_label = EKB_CONFIG.TIER_TO_LABEL.get(
            class_resp.final_security_tier, "unknown"
        )

        return OrchestratorRunResponse(
            gcs_uri=class_resp.final_original_uri,
            chunks_generated=ingest_resp.chunk_count,
            final_domain=class_resp.final_domain,
            security_tier=tier_label,
        )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: uv run python -m pipelines.enterprise_knowledge_base.app.orchestrator <project_id> <gcs_uri>"
        )
        sys.exit(1)

    proj_id = sys.argv[1]
    input_uri = sys.argv[2]

    pipeline = KBIngestionPipeline(proj_id)
    run_req = OrchestratorRunRequest(gcs_uri=input_uri)
    response = pipeline.run(run_req)
    print(response.model_dump_json(indent=2))
