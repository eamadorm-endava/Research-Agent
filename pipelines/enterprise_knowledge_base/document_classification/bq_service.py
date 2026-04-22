from google.cloud import bigquery
from loguru import logger
from .config import EKB_CONFIG


class BQService:
    """Service class for BigQuery operations: metadata persistence and queries.

    Handles streaming inserts of document metadata into the centralized
    knowledge base tables.
    """

    def __init__(self) -> None:
        """Initializes the BigQuery client using Application Default Credentials (ADC).

        Returns:
            None
        """
        self.client = bigquery.Client(project=EKB_CONFIG.PROJECT_ID)
        self.dataset_id = EKB_CONFIG.BQ_DATASET
        self.table_id = EKB_CONFIG.BQ_TABLE

    def insert_metadata(self, record_dict: dict) -> None:
        """Performs a streaming insert of a metadata record into BigQuery.

        Args:
            record_dict (dict): The metadata record to insert, matching the table schema.

        Returns:
            None

        Raises:
            RuntimeError: If the insertion fails.
        """
        table_ref = self.client.dataset(self.dataset_id).table(self.table_id)
        logger.info(
            f"Inserting metadata into BigQuery: {self.dataset_id}.{self.table_id}"
        )

        errors = self.client.insert_rows_json(table_ref, [record_dict])

        if errors:
            logger.error(f"Failed to insert rows into BigQuery: {errors}")
            raise RuntimeError(f"BigQuery insertion failed: {errors}")

        logger.info("BigQuery insertion successful.")
