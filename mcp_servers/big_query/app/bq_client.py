from typing import Optional, List, Dict, Any
import logging
import json
from google.cloud import bigquery
from google.cloud.bigquery.schema import SchemaField
from google.cloud.exceptions import GoogleCloudError, NotFound

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BigQueryManager:
    """
    Manager for Google Cloud BigQuery operations.
    Initializes a client using Application Default Credentials (ADC).
    """
    def __init__(self):
        try:
            self.client = bigquery.Client()
            logger.info(f"BigQuery Client initialized using ADC (Project: {self.client.project}).")
        except GoogleCloudError as e:
            logger.error(f"Failed to initialize BigQuery Client: {e}")
            raise

    def table_exists(self, project_id: str, dataset_id: str, table_id: str) -> bool:
        """
        Checks if a specific table exists in a dataset within a GCP project.

        Args:
            project_id (str): The GCP project ID.
            dataset_id (str): The ID of the dataset containing the table.
            table_id (str): The ID of the table to check.

        Returns:
            bool: True if the table exists, False otherwise.
        """
        full_table_id = f"{project_id}.{dataset_id}.{table_id}"
        try:
            self.client.get_table(full_table_id)
            return True
        except NotFound:
            return False
        except Exception as e:
            logger.error(f"Error checking if table exists {full_table_id}: {e}")
            raise

    def create_dataset(self, project_id: str, dataset_id: str, location: str) -> str:
        """
        Creates a new BigQuery dataset.

        Args:
            project_id (str): The GCP project ID.
            dataset_id (str): The ID for the new dataset.
            location (str): The geographic location for the dataset.

        Returns:
            str: The full dataset ID of the created or existing dataset.
        """
        try:
            full_dataset_id = f"{project_id}.{dataset_id}"
            dataset = bigquery.Dataset(full_dataset_id)
            dataset.location = location
            dataset = self.client.create_dataset(dataset, timeout=30, exists_ok=True)
            return str(dataset.reference)
        except Exception as e:
            logger.error(f"Error creating dataset {dataset_id} in project {project_id}: {e}")
            raise GoogleCloudError(f"Error creating dataset {dataset_id}: {e}")

    def list_datasets(self, project_id: str) -> List[str]:
        """
        Lists all datasets in a project.

        Args:
            project_id (str): The GCP project ID.

        Returns:
            List[str]: A list of dataset IDs as strings.
        """
        try:
            datasets = list(self.client.list_datasets(project=project_id))
            return [d.dataset_id for d in datasets]
        except Exception as e:
            logger.error(f"Error listing datasets for project {project_id}: {e}")
            raise GoogleCloudError(f"Error listing datasets for project {project_id}: {e}")

    def create_table(self, project_id: str, dataset_id: str, table_id: str, schema_json: List[Dict[str, Any]]) -> str:
        """
        Creates a new table in BigQuery with the specified schema.

        Args:
            project_id (str): The GCP project ID.
            dataset_id (str): The ID of the dataset.
            table_id (str): The ID for the new table.
            schema_json (List[Dict[str, Any]]): A list of dictionaries defining the schema.
                                                 Ex: [{"name": "id", "type": "INTEGER"}]

        Returns:
            str: The full table ID of the created or existing table.
        """
        try:
            full_table_id = f"{project_id}.{dataset_id}.{table_id}"
            schema = [bigquery.SchemaField.from_api_repr(field) for field in schema_json]
            table = bigquery.Table(full_table_id, schema=schema)
            table = self.client.create_table(table, exists_ok=True)
            return str(table.reference)
        except Exception as e:
            logger.error(f"Error creating table {table_id} in {project_id}.{dataset_id}: {e}")
            raise GoogleCloudError(f"Error creating table {table_id}: {e}")

    def get_table_schema(self, project_id: str, dataset_id: str, table_id: str) -> List[SchemaField]:
        """
        Retrieves the schema definition of an existing table.

        Args:
            project_id (str): The GCP project ID.
            dataset_id (str): The ID of the dataset.
            table_id (str): The ID of the table.

        Returns:
            List[SchemaField]: A list of SchemaField objects representing the table structure.
        """
        if not self.table_exists(project_id, dataset_id, table_id):
            raise ValueError(f"Table {table_id} does not exist in {project_id}.{dataset_id}.")

        full_table_id = f"{project_id}.{dataset_id}.{table_id}"
        try:
            table = self.client.get_table(full_table_id)
            return list(table.schema)
        except Exception as e:
            raise ValueError(f"Error getting table schema for {full_table_id}: {e}")

    def list_tables(self, project_id: str, dataset_id: str) -> List[str]:
        """
        Lists the names of all tables within a specific dataset.

        Args:
            project_id (str): The GCP project ID.
            dataset_id (str): The ID of the dataset.

        Returns:
            List[str]: A list of table IDs as strings.
        """
        try:
            tables = self.client.list_tables(f"{project_id}.{dataset_id}")
            return [table.table_id for table in tables]
        except Exception as e:
            logger.error(f"Error listing tables in {project_id}.{dataset_id}: {e}")
            raise GoogleCloudError(f"Error listing tables in {dataset_id}: {e}")

    def insert_rows(self, project_id: str, dataset_id: str, table_id: str, rows: List[Dict[str, Any]]) -> None:
        """
        Inserts multiple rows into an existing table using a load job.

        Args:
            project_id (str): The GCP project ID.
            dataset_id (str): The ID of the dataset.
            table_id (str): The ID of the target table.
            rows (List[Dict[str, Any]]): A list of dictionaries, where each dict represents a row to insert.
        """
        if not self.table_exists(project_id, dataset_id, table_id):
            raise ValueError(f"Table {table_id} does not exist in {project_id}.{dataset_id}.")

        full_table_id = f"{project_id}.{dataset_id}.{table_id}"
        try:
            # Retrieve schema to preserve field modes (preventing them from resetting to NULLABLE)
            schema = self.get_table_schema(project_id, dataset_id, table_id)
            
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                schema=schema
            )
            load_job = self.client.load_table_from_json(rows, full_table_id, job_config=job_config)
            load_job.result()
        except Exception as e:
            raise ValueError(f"Error inserting rows into {full_table_id}: {e}")

    def execute_query(self, project_id: str, query: str) -> List[Dict[str, Any]]:
        """
        Executes a SQL query against BigQuery and returns the results.

        Args:
            project_id (str): The GCP project ID.
            query (str): The SQL query string.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dict represents a result row.
        """
        try:
            query_job = self.client.query(query, project=project_id)
            results = query_job.result()
            
            # Convert results to a list of dicts for easier handling/serialization
            output = [dict(row) for row in results]
            
            def make_serializable(obj):
                if isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_serializable(v) for v in obj]
                else:
                    try:
                        json.dumps(obj)
                        return obj
                    except (TypeError, ValueError):
                        return str(obj)
            return make_serializable(output)
        except Exception as e:
            raise ValueError(f"Error querying the data: {e}")
