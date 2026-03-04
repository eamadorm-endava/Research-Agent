from typing import Optional, List, Dict, Any
import logging
import json
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

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

    def create_dataset(self, dataset_id: str, location: str = "US") -> str:
        """
        Creates a new BigQuery dataset.
        
        Args:
            dataset_id: The ID of the dataset to create (e.g., 'my_dataset').
            location: Data location.
            
        Returns:
            str: The full dataset ID.
        """
        try:
            full_dataset_id = f"{self.client.project}.{dataset_id}"
            dataset = bigquery.Dataset(full_dataset_id)
            dataset.location = location
            dataset = self.client.create_dataset(dataset, exists_ok=True)
            logger.info(f"Dataset {dataset.dataset_id} created or already exists.")
            return dataset.full_dataset_id
        except GoogleCloudError as e:
            logger.error(f"Error creating dataset {dataset_id}: {e}")
            raise

    def create_table(self, dataset_id: str, table_id: str, schema_json: List[Dict[str, str]]) -> str:
        """
        Creates a new table in BigQuery.
        
        Args:
            dataset_id: The existing dataset ID.
            table_id: The target table ID.
            schema_json: A list of dicts defining the schema, e.g., [{"name": "id", "type": "INTEGER"}]
            
        Returns:
            str: The full table ID.
        """
        try:
            full_table_id = f"{self.client.project}.{dataset_id}.{table_id}"
            schema = [bigquery.SchemaField.from_api_repr(field) for field in schema_json]
            table = bigquery.Table(full_table_id, schema=schema)
            table = self.client.create_table(table, exists_ok=True)
            logger.info(f"Table {table.table_id} created or already exists.")
            return table.full_table_id
        except GoogleCloudError as e:
            logger.error(f"Error creating table {table_id}: {e}")
            raise

    def get_table_schema(self, dataset_id: str, table_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the schema of a specific table.
        
        Args:
            dataset_id: Dataset ID.
            table_id: Table ID.
            
        Returns:
            List[Dict[str, Any]]: The schema definition.
        """
        try:
            full_table_id = f"{self.client.project}.{dataset_id}.{table_id}"
            table = self.client.get_table(full_table_id)
            return [field.to_api_repr() for field in table.schema]
        except GoogleCloudError as e:
            logger.error(f"Error fetching schema for {table_id}: {e}")
            raise

    def list_tables(self, dataset_id: str) -> List[str]:
        """
        Lists all tables in a specific dataset.
        
        Args:
            dataset_id: The dataset ID.
            
        Returns:
            List[str]: A list of table IDs.
        """
        try:
            tables = self.client.list_tables(dataset_id)
            return [table.table_id for table in tables]
        except GoogleCloudError as e:
            logger.error(f"Error listing tables in {dataset_id}: {e}")
            raise

    def insert_rows(self, dataset_id: str, table_id: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Inserts rows into an existing BigQuery table using streaming API.
        
        Args:
            dataset_id: Dataset ID.
            table_id: Table ID.
            rows: List of dicts representing the rows to insert.
            
        Returns:
            Dict[str, Any]: Success status or list of errors.
        """
        try:
            full_table_id = f"{self.client.project}.{dataset_id}.{table_id}"
            errors = self.client.insert_rows_json(full_table_id, rows)
            if not errors:
                logger.info(f"Loaded {len(rows)} rows into {full_table_id}.")
                return {"status": "success", "inserted": len(rows)}
            else:
                logger.error(f"Errors occurred while inserting rows: {errors}")
                return {"status": "error", "errors": errors}
        except GoogleCloudError as e:
            logger.error(f"Error inserting rows into {table_id}: {e}")
            raise

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes a SQL query and safely returns the results, converting complex types (Struct/Arrays) 
        into standard Python dictionaries/lists.
        
        Args:
            query: The standard SQL query.
            
        Returns:
            List[Dict[str, Any]]: The query results as a list of dicts.
        """
        try:
            query_job = self.client.query(query)
            results = query_job.result() # Wait for job to finish
            
            output = []
            for row in results:
                # dict(row) internally handles simple types and converts structs 
                # to dictionaries if using standard settings, but we can enforce safety
                row_dict = dict(row)
                output.append(row_dict)
                
            logger.info(f"Query returned {len(output)} rows.")
            
            # Simple recursive helper to ensure JSON serializability for the MCP return payload
            def make_serializable(obj):
                if isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_serializable(v) for v in obj]
                else:
                    # Rely on JSON dumping to catch weird types gracefully
                    try:
                        json.dumps(obj)
                        return obj
                    except (TypeError, ValueError):
                        return str(obj)
                        
            return make_serializable(output)
        except GoogleCloudError as e:
            logger.error(f"Error executing query: {e}")
            raise
