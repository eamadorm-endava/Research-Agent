from fastapi import FastAPI, HTTPException
from loguru import logger

from .orchestrator import KBIngestionPipeline
from .schemas import OrchestratorRunRequest, OrchestratorRunResponse
from .document_classification.config import EKB_CONFIG

app = FastAPI(
    title="EKB Ingestion Service",
    description="HTTP wrapper for the Enterprise Knowledge Base ingestion pipeline.",
    version="1.0.0",
)


@app.post("/ingest", response_model=OrchestratorRunResponse)
def ingest_document(request: OrchestratorRunRequest) -> OrchestratorRunResponse:
    """
    Triggers the EKB pipeline for a given GCS URI.
    Runs synchronously to allow FastAPI to offload it to an external threadpool.
    """
    logger.info(f"Received ingestion request for URI: {request.gcs_uri}")
    try:
        pipeline = KBIngestionPipeline(EKB_CONFIG.PROJECT_ID)
        response = pipeline.run(request)
        logger.info(f"Successfully processed URI: {request.gcs_uri}")
        return response
    except Exception as e:
        logger.error(f"Pipeline execution failed for {request.gcs_uri}: {e}")
        # In a production environment, you might want to log the full stack trace
        raise HTTPException(
            status_code=500, detail=f"Pipeline execution failed: {str(e)}"
        )
