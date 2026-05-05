from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
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
from .cloud_tasks import CloudTasksService

app = FastAPI(
    title="EKB Ingestion Service",
    description="HTTP wrapper for the Enterprise Knowledge Base ingestion pipeline.",
    version="1.1.0",
)

job_service = JobService()
ekb_pipeline = KBIngestionPipeline(EKB_CONFIG.PROJECT_ID)
cloud_tasks_service = CloudTasksService()


def run_pipeline_task(job_id: str, request: OrchestratorRunRequest) -> None:
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
        result = ekb_pipeline.run(request)

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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=OrchestratorRunResponse)
async def ingest_document(
    request: OrchestratorRunRequest, fastapi_req: Request
) -> OrchestratorRunResponse:
    """
    Triggers the EKB pipeline by pushing a Cloud Task.
    Returns a Job ID for status tracking.

    Args:
        request: OrchestratorRunRequest -> The document URI to ingest.
        fastapi_req: Request -> FastAPI request object for url resolving.

    Returns:
        OrchestratorRunResponse -> The initial job status and ID.
    """
    logger.info(f"Received ingestion request for URI: {request.gcs_uri}")
    try:
        filename = request.filename
        job_id = job_service.create_job(filename)

        service_url = str(fastapi_req.base_url)
        cloud_tasks_service.enqueue_ingestion_task(
            job_id, request.model_dump(), service_url
        )

        return OrchestratorRunResponse(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            message="File processing task enqueued successfully.",
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
    logger.info(f"Checking status for job_id: {job_id}")
    status = job_service.get_job_status(job_id)
    if not status:
        logger.warning(f"Job {job_id} not found during status check.")
        raise HTTPException(status_code=404, detail="Job not found")

    logger.debug(f"Status for {job_id}: {status.status.value}")
    return status


class TaskPayload(BaseModel):
    job_id: str
    request: OrchestratorRunRequest


@app.post("/task-handler")
async def handle_task(payload: TaskPayload) -> dict:
    """
    Synchronous execution of the pipeline, triggered by Cloud Tasks.
    This maintains an active HTTP connection so Cloud Run can scale horizontally
    and allocate full CPU resources.
    """
    logger.info(f"Received Cloud Task for job_id: {payload.job_id}")
    run_pipeline_task(payload.job_id, payload.request)
    return {"status": "success"}
