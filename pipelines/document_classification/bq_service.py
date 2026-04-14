from google.cloud import bigquery
from loguru import logger
from .config import EKB_CONFIG
from datetime import datetime


class BQService:
    """Service class for BigQuery metadata persistence and resource management.

    Responsible for ensuring datasets and tables exist, and logging final
    classification results into the EKB metadata table.
    """

    def __init__(self, project_id: str = EKB_CONFIG.PROJECT_ID):
        """Initializes the BigQuery client using ADC.

        Args:
            project_id (str): The GCP project ID.
        """
        self.client = bigquery.Client(project=project_id)
        self.project = project_id
        self.dataset_id = f"{project_id}.{EKB_CONFIG.BQ_DATASET}"
        self.table_id = f"{self.dataset_id}.{EKB_CONFIG.BQ_TABLE}"

    def ensure_dataset_exists(self) -> None:
        """Checks if the configured dataset exists; if not, creates it.

        Returns:
            None
        """
        try:
            self.client.get_dataset(self.dataset_id)
        except Exception:
            logger.info(
                f"Dataset {self.dataset_id} not found. Creating in {EKB_CONFIG.LOCATION}..."
            )
            dataset = bigquery.Dataset(self.dataset_id)
            dataset.location = EKB_CONFIG.LOCATION
            self.client.create_dataset(dataset, timeout=30)
            logger.info(f"Dataset {self.dataset_id} created successfully.")

    def insert_document_metadata(self, metadata: dict) -> bool:
        """Inserts document metadata as a new row in BigQuery, ensuring tables exist.

        Args:
            metadata (dict): Data mapping to the EKB schema fields.

        Returns:
            bool: True if successful, raises exception otherwise.
        """
        # Ensure infrastructure exists before insertion
        self.ensure_dataset_exists()
        self.create_table_if_not_exists()

        logger.info(f"Logging metadata to BigQuery for: {metadata.get('filename')}")

        if "ingested_at" not in metadata:
            metadata["ingested_at"] = datetime.now().isoformat()

        metadata["routed_at"] = datetime.now().isoformat()

        errors = self.client.insert_rows_json(self.table_id, [metadata])

        if not errors:
            logger.info("Metadata successfully logged to BigQuery.")
            return True
        else:
            logger.error(f"Errors occurred during BigQuery insertion: {errors}")
            raise Exception("BigQuery Insert Failure")

    def create_table_if_not_exists(self) -> None:
        """Utility to ensure the metadata table exists with the correct schema.
        Configures the table with day-partitioning on 'ingested_at' and clustering
        on 'domain', 'project', and 'classification_tier'.

        Returns:
            None
        """
        schema = [
            bigquery.SchemaField("document_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("gcs_uri", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_uri", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("filename", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("classification_tier", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("domain", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("confidence_score", "FLOAT64"),
            bigquery.SchemaField("trust_level", "STRING"),
            bigquery.SchemaField("project", "STRING"),
            bigquery.SchemaField("uploader_email", "STRING"),
            bigquery.SchemaField("creator_name", "STRING"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("routed_at", "TIMESTAMP"),
            bigquery.SchemaField("description", "STRING"),
            bigquery.SchemaField("vectorization_status", "STRING"),
        ]

        table = bigquery.Table(self.table_id, schema=schema)
        table.partitioning_type = "DAY"
        table.partitioning_field = "ingested_at"
        table.clustering_fields = ["domain", "project", "classification_tier"]

        try:
            self.client.create_table(table, exists_ok=True)
            logger.info(f"BigQuery table verified/created: {self.table_id}")
        except Exception as e:
            logger.warning(f"Error verifying/creating BigQuery table: {str(e)}")
