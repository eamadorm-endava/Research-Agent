"""
Placeholder orchestrator for the Enterprise Knowledge Base ingestion pipeline.
"""

import sys
from .rag_ingestion import (
    RAGIngestion,
    IngestDocumentRequest,
)
from .document_classification.pipeline import ClassificationPipeline
from loguru import logger


class KBIngestionPipeline:
    """Orchestrates the ingestion, classification, and vectorization of documents."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.classification_pipeline = ClassificationPipeline()
        self.rag_pipeline = RAGIngestion()

    def trigger_pipeline(self, gcs_uri: str) -> None:
        """
        Orchestrates the entire ingestion process.
        """
        logger.info(f"Triggering KB Ingestion Pipeline for: {gcs_uri}")

        # 1. Execute Classification Pipeline
        logger.info("Step 1: Running Document Classification...")
        class_resp = self.classification_pipeline.run(gcs_uri)
        logger.info(f"Classification complete. Domain: {class_resp.final_domain}")

        # 2. Execute end-to-end RAG pipeline
        logger.info(
            f"Step 2: Running RAG Ingestion for {class_resp.final_sanitized_uri}..."
        )
        ingest_req = IngestDocumentRequest(gcs_uri=class_resp.final_sanitized_uri)
        ingest_resp = self.rag_pipeline.run(ingest_req)

        if "SUCCESS" in ingest_resp.execution_status:
            logger.info(
                f"Pipeline finished successfully. Chunks: {ingest_resp.chunk_count}"
            )
        else:
            logger.warning(
                f"Pipeline finished with status: {ingest_resp.execution_status}"
            )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: uv run python -m pipelines.enterprise_knowledge_base.orchestrator <project_id> <gcs_uri>"
        )
        sys.exit(1)

    project_id = sys.argv[1]
    gcs_uri = sys.argv[2]

    pipeline = KBIngestionPipeline(project_id)
    pipeline.trigger_pipeline(gcs_uri)
