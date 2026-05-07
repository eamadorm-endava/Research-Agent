import asyncio
import sys
from fastapi import FastAPI, HTTPException, Request
from loguru import logger

from .orchestrator import KBIngestionPipeline
from .schemas import (
    OrchestratorRunRequest,
    OrchestratorRunResponse,
    JobStatusResponse,
    JobStatus,
)
from .jobs import JobService
from .cloud_tasks.service import CloudTasksService
from .cloud_tasks.schemas import TaskPayload


def custom_log_format(record: dict) -> str:
    """
    Dynamically injects the job_id into the loguru format if it exists in the record extra context.

    Args:
        record: dict -> The loguru record dictionary containing context and log data.

    Returns:
        str -> The customized log format string.
    """
    if "job_id" in record["extra"] and record["extra"]["job_id"]:
        return "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | {extra[job_id]} - <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"
    else:
        return "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"


logger.remove()
logger.add(sys.stdout, format=custom_log_format)

app = FastAPI(
    title="EKB Ingestion Service",
    description="HTTP wrapper for the Enterprise Knowledge Base ingestion pipeline.",
    version="1.1.0",
)

job_service = JobService()
cloud_tasks_service = CloudTasksService()
ekb_pipeline = KBIngestionPipeline()


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
        job_id = await asyncio.to_thread(job_service.create_job, filename)

        service_url = str(fastapi_req.base_url)
        await asyncio.to_thread(
            cloud_tasks_service.enqueue_ingestion_task,
            job_id,
            request.model_dump(),
            service_url,
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


@app.post("/task-handler")
async def handle_task(payload: TaskPayload) -> dict:
    """
    Executes the full pipeline for a single document, triggered by Cloud Tasks.
    Holds the HTTP connection open until completion so Cloud Tasks can track success or failure.

    Args:
        payload: TaskPayload -> Contains the job_id and the original ingestion request.

    Returns:
        dict -> A status dict with key 'status' set to 'success' on completion.
    """
    with logger.contextualize(job_id=payload.job_id):
        logger.info(f"Received Cloud Task for job_id: {payload.job_id}")
        try:
            result = await asyncio.to_thread(ekb_pipeline.run, payload.request)

            metadata = {
                "gcs_uri": result.gcs_uri,
                "chunks_generated": result.chunks_generated,
                "final_domain": result.final_domain,
                "security_tier": result.security_tier,
            }

            job_service.update_job(
                job_id=payload.job_id,
                status=JobStatus.SUCCESS,
                message="Pipeline completed successfully.",
                metadata=metadata,
            )
            logger.success(f"Job {payload.job_id} completed successfully.")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Job {payload.job_id} failed: {e}")
            job_service.update_job(
                job_id=payload.job_id,
                status=JobStatus.ERROR,
                message=f"Pipeline failed: {str(e)}",
            )
            raise HTTPException(status_code=500, detail=str(e))
