"""
Placeholder orchestrator for the Enterprise Knowledge Base ingestion pipeline.
"""

import sys
from pipelines.enterprise_knowledge_base.rag_ingestion import RAGIngestion
from pipelines.enterprise_knowledge_base.document_classification.pipeline import ClassificationPipeline

class KBIngestionPipeline:
    """Orchestrates the ingestion, classification, and vectorization of documents."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.rag_pipeline = RAGIngestion(project_id=self.project_id)
        self.classification_pipeline = ClassificationPipeline()

    def trigger_pipeline(self, gcs_uri: str) -> None:
        """
        Executes the staging and vectorization pipeline for a given document.
        """
        print(f"Triggering pipeline for {gcs_uri}...")
        
        # 1. Document Classification
        print("Starting Document Classification Phase...")
        dlp_response = self.classification_pipeline.dlp_trigger(gcs_uri)
        print(f"DLP trigger response: tier={dlp_response.proposed_classification_tier}, sanitized_uri={dlp_response.sanitized_gcs_uri}")
        
        classification_result = self.classification_pipeline.contextual_classification(
            sanitized_url=dlp_response.sanitized_gcs_uri,
            proposed_classification_tier=dlp_response.proposed_classification_tier,
            proposed_domain=None,
            trust_level=None
        )
        print(f"Contextual Classification completed: tier={classification_result.final_classification_tier}, domain={classification_result.domain}")
        
        # Use the sanitized URI for RAG Ingestion
        target_uri = dlp_response.sanitized_gcs_uri
        
        # 2. Parse, chunk, and stage into BigQuery
        print(f"Starting RAG Ingestion for {target_uri}...")
        chunk_count = self.rag_pipeline.run_staging(target_uri)
        print(f"Successfully staged {chunk_count} chunks.")
        
        # 3. Programmatically trigger vectorization via BQML
        if chunk_count > 0:
            print("Initiating BigQuery ML vectorization...")
            self.rag_pipeline.generate_embeddings(target_uri)
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
