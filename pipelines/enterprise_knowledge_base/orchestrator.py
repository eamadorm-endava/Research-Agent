"""
Placeholder orchestrator for the Enterprise Knowledge Base ingestion pipeline.
"""

import sys
from pipelines.enterprise_knowledge_base.rag_ingestion import RAGIngestion

class KBIngestionPipeline:
    """Orchestrates the ingestion, classification, and vectorization of documents."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.rag_pipeline = RAGIngestion(project_id=self.project_id)

    def trigger_pipeline(self, gcs_uri: str) -> None:
        """
        Executes the staging and vectorization pipeline for a given document.
        """
        print(f"Triggering pipeline for {gcs_uri}...")
        
        # 1. Parse, chunk, and stage into BigQuery
        chunk_count = self.rag_pipeline.run_staging(gcs_uri)
        print(f"Successfully staged {chunk_count} chunks.")
        
        # 2. Programmatically trigger vectorization via BQML
        if chunk_count > 0:
            print("Initiating BigQuery ML vectorization...")
            self.rag_pipeline.generate_embeddings(gcs_uri)
            print("Vectorization complete.")
        else:
            print("No chunks to vectorize.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: uv run python -m pipelines.enterprise_knowledge_base.orchestrator <project_id> <gcs_uri>")
        sys.exit(1)
        
    project_id = sys.argv[1]
    gcs_uri = sys.argv[2]
    
    pipeline = KBIngestionPipeline(project_id)
    pipeline.trigger_pipeline(gcs_uri)
