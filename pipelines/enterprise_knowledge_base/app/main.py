from fastapi import FastAPI, HTTPException, BackgroundTasks
from loguru import logger

from .orchestrator import KBIngestionPipeline
from .schemas import (
    OrchestratorRunRequest,
    OrchestratorRunResponse,
    JobStatusResponse,
    JobStatus,
)
from .document_classification.config import EKB_CONFIG
from .jobs import JobService

app = FastAPI(
    title="EKB Ingestion Service",
    description="HTTP wrapper for the Enterprise Knowledge Base ingestion pipeline.",
    version="1.1.0",
)

job_service = JobService()


async def run_pipeline_task(job_id: str, request: OrchestratorRunRequest):
    """
    Background task to execute the sequential EKB pipeline (Classification -> RAG).
    Updates the BigQuery job status upon completion or failure.

    Args:
        job_id: str -> The unique identifier of the background job.
        request: OrchestratorRunRequest -> The request containing the source GCS URI.

    Returns:
        None
    """
    logger.info(f"Starting background pipeline for job {job_id}")
    try:
        pipeline = KBIngestionPipeline(EKB_CONFIG.PROJECT_ID)
        result = pipeline.run(request)

        # Extract metadata for status update
        metadata = {
            "gcs_uri": result.gcs_uri,
            "chunks_generated": result.chunks_generated,
            "final_domain": result.final_domain,
            "security_tier": result.security_tier,
        }

        job_service.update_job(
            job_id=job_id,
            status=JobStatus.SUCCESS,
            message="Pipeline completed successfully.",
            metadata=metadata,
        )
        logger.info(f"Job {job_id} completed successfully.")
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        job_service.update_job(
            job_id=job_id, status=JobStatus.ERROR, message=f"Pipeline failed: {str(e)}"
        )


@app.post("/ingest", response_model=OrchestratorRunResponse)
async def ingest_document(
    request: OrchestratorRunRequest, background_tasks: BackgroundTasks
) -> OrchestratorRunResponse:
    """
    Triggers the EKB pipeline asynchronously using a non-blocking job-based workflow.
    Returns a Job ID for status tracking.

    Args:
        request: OrchestratorRunRequest -> The document URI to ingest.
        background_tasks: BackgroundTasks -> FastAPI utility for background processing.

    Returns:
        OrchestratorRunResponse -> The initial job status and ID.
    """
    logger.info(f"Received ingestion request for URI: {request.gcs_uri}")
    try:
        filename = request.filename
        job_id = job_service.create_job(filename)

        background_tasks.add_task(run_pipeline_task, job_id, request)

        return OrchestratorRunResponse(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            message="File processing started. It might take up to 10 minutes to finish.",
        )
    except Exception as e:
        logger.error(f"Failed to initiate ingestion for {request.gcs_uri}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate ingestion: {str(e)}"
        )


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str) -> JobStatusResponse:
    """
    Retrieves the current progress and results of a specific ingestion job.

    Args:
        job_id: str -> The unique identifier of the job to check.

    Returns:
        JobStatusResponse -> The current status and extracted metadata.
    """
    status = job_service.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status
