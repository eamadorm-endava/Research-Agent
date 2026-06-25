import asyncio

from google.cloud import bigquery
from loguru import logger

from .schemas import InsertMetricsRequest, InsertMetricsResponse


class MetricsBQService:
    """Service for interacting with BigQuery to store agent metrics."""

    def __init__(self, project_id: str, dataset_id: str, table_id: str):
        """Initializes the BigQuery service.

        Args:
            project_id: str -> The GCP project ID.
            dataset_id: str -> The BigQuery dataset ID.
            table_id: str -> The BigQuery table ID.
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        self._client = None

    @property
    def client(self) -> bigquery.Client:
        """Lazily instantiates the BigQuery client.

        Returns:
            bigquery.Client -> The initialized BigQuery client.
        """
        if self._client is None:
            self._client = bigquery.Client()
        return self._client

    async def insert_metrics(
        self, request: InsertMetricsRequest
    ) -> InsertMetricsResponse:
        """Asynchronously inserts a metrics record into BigQuery.

        Args:
            request: InsertMetricsRequest -> The request payload containing the metrics.

        Returns:
            InsertMetricsResponse -> The result of the insertion operation.
        """
        try:
            row_data = request.record.model_dump(mode="json")

            # Run the blocking BigQuery call in a separate thread
            errors = await asyncio.to_thread(
                self.client.insert_rows_json, self.table_ref, [row_data]
            )

            if errors:
                logger.error(
                    f"Failed to insert response time metrics to BigQuery: {errors}"
                )
                return InsertMetricsResponse(success=False, error_message=str(errors))

            logger.info(
                f"Successfully logged response time metrics to BigQuery for session {request.record.session_id}"
            )
            return InsertMetricsResponse(success=True)

        except Exception as e:
            logger.error(f"Error logging metrics to BigQuery: {e}")
            return InsertMetricsResponse(success=False, error_message=str(e))
