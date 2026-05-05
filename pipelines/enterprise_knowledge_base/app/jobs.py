import uuid
from datetime import datetime
from typing import Optional
from google.cloud import bigquery
from loguru import logger

from .schemas import JobStatus, JobStatusResponse
from .config import EKB_CONFIG


# Global client to share connection pool across multiple requests
bq_client = bigquery.Client(project=EKB_CONFIG.PROJECT_ID)


class JobService:
    """Manages the persistence of ingestion job statuses in BigQuery."""

    bq_client = bq_client

    def __init__(self):
        self.table_id = f"{EKB_CONFIG.PROJECT_ID}.{EKB_CONFIG.BQ_DATASET}.{EKB_CONFIG.BQ_JOBS_TABLE}"

    def create_job(self, filename: str) -> str:
        """
        Creates a new ingestion job record in BigQuery to track background progress.
        The job_id is generated using uuid5 based on the filename and ingestion timestamp
        to ensure uniqueness and traceability.

        Args:
            filename: str -> The basename of the file being processed.

        Returns:
            str -> The unique UUID generated for the job.
        """
        start_time = datetime.utcnow().isoformat()
        # Generate a deterministic UUID based on filename and timestamp for uniqueness
        job_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{filename}-{start_time}"))

        rows_to_insert = [
            {
                "job_id": job_id,
                "filename": filename,
                "status": JobStatus.PROCESSING.value,
                "message": "Job initiated. Starting classification and ingestion.",
                "start_time": start_time,
            }
        ]
        logger.info(f"Creating job record for {filename}: {job_id}")
        load_job = self.bq_client.load_table_from_json(rows_to_insert, self.table_id)
        load_job.result()  # Wait for completion to ensure DML consistency
        return job_id

    def update_job(
        self,
        job_id: str,
        status: JobStatus,
        message: str,
        metadata: Optional[dict] = None,
    ):
        """
        Updates an existing job record with its final status and processing metadata.

        Args:
            job_id: str -> The unique identifier of the job to update.
            status: JobStatus -> The new status (SUCCESS, ERROR, etc.).
            message: str -> Informational or error message.
            metadata: Optional[dict] -> Additional results (chunks, domain, etc.).

        Returns:
            None
        """
        logger.info(f"Updating job {job_id} to {status.value}")

        # Use DML for updates
        query = f"""
            UPDATE `{self.table_id}`
            SET status = @status,
                message = @message,
                end_time = @end_time,
                metadata = @metadata
            WHERE job_id = @job_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("status", "STRING", status.value),
                bigquery.ScalarQueryParameter("message", "STRING", message),
                bigquery.ScalarQueryParameter(
                    "end_time", "STRING", datetime.utcnow().isoformat()
                ),
                bigquery.ScalarQueryParameter(
                    "metadata", "STRING", str(metadata) if metadata else None
                ),
                bigquery.ScalarQueryParameter("job_id", "STRING", job_id),
            ]
        )
        query_job = self.bq_client.query(query, job_config=job_config)
        query_job.result()  # Wait for completion

    def get_job_status(self, job_id: str) -> Optional[JobStatusResponse]:
        """
        Retrieves the current status and metadata of a specific job from BigQuery.

        Args:
            job_id: str -> The unique identifier of the job to retrieve.

        Returns:
            Optional[JobStatusResponse] -> The hydrated response object or None if not found.
        """
        query = f"SELECT * FROM `{self.table_id}` WHERE job_id = @job_id"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
        )
        query_job = self.bq_client.query(query, job_config=job_config)
        results = list(query_job.result())

        if not results:
            return None

        row = results[0]
        # Metadata is stored as a stringified dict in this simple impl
        meta_str = row.get("metadata")
        meta = eval(meta_str) if meta_str else {}

        return JobStatusResponse(
            job_id=row.job_id,
            status=JobStatus(row.status),
            message=row.message,
            gcs_uri=meta.get("gcs_uri"),
            chunks_generated=meta.get("chunks_generated"),
            final_domain=meta.get("final_domain"),
            security_tier=meta.get("security_tier"),
        )
