from typing import Any, Dict, List, Optional
import logging
import json
import httpx
from google.cloud import bigquery
from google.cloud.bigquery.schema import SchemaField
from google.cloud.exceptions import GoogleCloudError, NotFound
from google.oauth2.credentials import Credentials

from .config import BIGQUERY_API_CONFIG, BIGQUERY_AUTH_CONFIG
from .schemas import AuthenticationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BigQueryManager:
    """
    Manager for Google Cloud BigQuery operations.
    Initializes a client using delegated Google credentials.
    """

    def __init__(self, creds: Credentials, default_project: Optional[str] = None):
        self.creds = creds
        self.default_project = default_project
        try:
            self.client = bigquery.Client(
                credentials=self.creds, project=self.default_project
            )
            logger.info(
                f"BigQuery client initialized using delegated user credentials (Project: {self.client.project})."
            )
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
            logger.error(
                f"Error creating dataset {dataset_id} in project {project_id}: {e}"
            )
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
            raise GoogleCloudError(
                f"Error listing datasets for project {project_id}: {e}"
            )

    def create_table(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        schema_json: List[Dict[str, Any]],
    ) -> str:
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
            schema = [
                bigquery.SchemaField.from_api_repr(field) for field in schema_json
            ]
            table = bigquery.Table(full_table_id, schema=schema)
            table = self.client.create_table(table, exists_ok=True)
            return str(table.reference)
        except Exception as e:
            logger.error(
                f"Error creating table {table_id} in {project_id}.{dataset_id}: {e}"
            )
            raise GoogleCloudError(f"Error creating table {table_id}: {e}")

    def get_table_schema(
        self, project_id: str, dataset_id: str, table_id: str
    ) -> List[SchemaField]:
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
            raise ValueError(
                f"Table {table_id} does not exist in {project_id}.{dataset_id}."
            )

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

    def insert_rows(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        rows: List[Dict[str, Any]],
    ) -> None:
        """
        Inserts multiple rows into an existing table using a load job.

        Args:
            project_id (str): The GCP project ID.
            dataset_id (str): The ID of the dataset.
            table_id (str): The ID of the target table.
            rows (List[Dict[str, Any]]): A list of dictionaries, where each dict represents a row to insert.
        """
        if not self.table_exists(project_id, dataset_id, table_id):
            raise ValueError(
                f"Table {table_id} does not exist in {project_id}.{dataset_id}."
            )

        full_table_id = f"{project_id}.{dataset_id}.{table_id}"
        try:
            # Retrieve schema to preserve field modes (preventing them from resetting to NULLABLE)
            schema = self.get_table_schema(project_id, dataset_id, table_id)

            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                schema=schema,
            )
            load_job = self.client.load_table_from_json(
                rows, full_table_id, job_config=job_config
            )
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


def build_bq_credentials(
    *,
    access_token: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    validate: bool = True,
) -> Credentials:
    """
    Builds Google OAuth2 credentials for BigQuery from a delegated access token.
    Args:
        access_token: Optional OAuth2 access token.
        validate: Whether to validate token validity before creating credentials.
    Return: A Google Credentials object.
    """

    scopes = scopes or list(BIGQUERY_API_CONFIG.read_write_scopes)

    if access_token:
        if validate:
            validate_access_token(access_token, scopes)
        return Credentials(token=access_token, scopes=scopes)

    raise RuntimeError(
        "No BigQuery credentials available. Provide a delegated user access token header."
    )


def validate_access_token(
    access_token: str, required_scopes: Optional[List[str]] = None
) -> dict[str, Any]:
    """
    Validates an OAuth access token against Google's tokeninfo endpoint.
    Args:
        access_token: The OAuth2 access token to validate.
    Return: The token info payload when token is valid.
    """
    try:
        with httpx.Client() as client:
            response = client.get(
                BIGQUERY_AUTH_CONFIG.google_token_info_url,
                params={"access_token": access_token},
                timeout=10,
            )
    except Exception as exc:
        raise AuthenticationError(f"Failed to reach token validation endpoint: {exc}")

    if response.status_code != 200:
        try:
            error_detail = response.json().get("error_description", response.text)
        except Exception:
            error_detail = response.text
        raise AuthenticationError(f"Invalid OAuth token: {error_detail}")

    token_info = response.json()

    if required_scopes:
        token_scopes = set(token_info.get("scope", "").split())
        missing = [scope for scope in required_scopes if scope not in token_scopes]
        if missing:
            raise AuthenticationError(
                f"Token is missing required scopes: {', '.join(missing)}"
            )

    return token_info
