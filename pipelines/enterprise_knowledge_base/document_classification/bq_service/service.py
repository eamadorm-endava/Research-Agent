from google.cloud import bigquery
from loguru import logger
from ..config import EKB_CONFIG
from .schemas import (
    BQMetadataRecord,
    GetLatestVersionRequest,
    GetLatestVersionResponse,
    DeprecateVersionsRequest,
    DeprecateVersionsResponse,
)


class BQService:
    """Service class for BigQuery operations: metadata persistence and queries.

    Handles metadata insertion using Load Jobs to avoid streaming buffer limitations.
    """

    SCHEMA = [
        bigquery.SchemaField("document_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("gcs_uri", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("filename", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("classification_tier", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("domain", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("confidence_score", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("trust_level", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("uploader_email", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("description", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("version", "INT64", mode="REQUIRED"),
        bigquery.SchemaField("latest", "BOOL", mode="REQUIRED"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
    ]

    def __init__(self) -> None:
        """Initializes the BigQuery client using Application Default Credentials (ADC).

        Returns:
            None
        """
        self.client = bigquery.Client(project=EKB_CONFIG.PROJECT_ID)
        self.dataset_id = EKB_CONFIG.BQ_DATASET
        self.table_id = EKB_CONFIG.BQ_TABLE

    def insert_metadata(self, record: BQMetadataRecord) -> bool:
        """Performs a Load Job insert of a metadata record into BigQuery.

        Uses load_table_from_json to bypass the streaming buffer, allowing
        immediate DML updates on the records.

        Args:
            record (BQMetadataRecord): The structured metadata record to insert.

        Returns:
            bool: True if the insertion was successful.

        Raises:
            RuntimeError: If the load job fails.
        """
        table_ref = f"{self.client.project}.{self.dataset_id}.{self.table_id}"
        logger.info(f"Loading metadata into BigQuery table: {table_ref}")

        # Convert Pydantic model to list of dict for Load Job
        record_dict = record.model_dump()

        job_config = bigquery.LoadJobConfig(
            schema=self.SCHEMA,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        # load_table_from_json expects a list of dictionaries
        load_job = self.client.load_table_from_json(
            [record_dict], table_ref, job_config=job_config
        )

        logger.info(f"Started Load Job: {load_job.job_id}")
        load_job.result()  # Wait for the job to complete

        if load_job.errors:
            logger.error(f"Load Job failed with errors: {load_job.errors}")
            raise RuntimeError(f"BigQuery Load Job failed: {load_job.errors}")

        logger.info("BigQuery Load Job successful.")
        return True

    def get_latest_version(
        self, request: GetLatestVersionRequest
    ) -> GetLatestVersionResponse:
        """Queries the max version for a given document_id.

        Args:
            request (GetLatestVersionRequest): The document identifier.

        Returns:
            GetLatestVersionResponse: The highest version number found.
        """
        query = f"""
            SELECT MAX(version) as max_version
            FROM `{self.client.project}.{self.dataset_id}.{self.table_id}`
            WHERE document_id = @doc_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("doc_id", "STRING", request.document_id)
            ]
        )
        logger.info(f"Checking latest version for document: {request.document_id}")
        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()

        current_version = 0
        for row in results:
            if row.max_version is not None:
                current_version = row.max_version

        return GetLatestVersionResponse(current_version=current_version)

    def deprecate_old_versions(
        self, request: DeprecateVersionsRequest
    ) -> DeprecateVersionsResponse:
        """Sets latest=False for all existing records of a document_id.

        Args:
            request (DeprecateVersionsRequest): The document identifier.

        Returns:
            DeprecateVersionsResponse: The number of rows updated.
        """
        query = f"""
            UPDATE `{self.client.project}.{self.dataset_id}.{self.table_id}`
            SET latest = FALSE
            WHERE document_id = @doc_id AND latest = TRUE
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("doc_id", "STRING", request.document_id)
            ]
        )
        logger.info(f"Deprecating old versions for document: {request.document_id}")
        query_job = self.client.query(query, job_config=job_config)
        query_job.result()  # Wait for DML to complete

        return DeprecateVersionsResponse(
            updated_count=query_job.num_dml_affected_rows or 0
        )
