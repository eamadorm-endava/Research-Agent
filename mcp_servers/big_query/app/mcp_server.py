from mcp.server.fastmcp import FastMCP
from mcp_servers.big_query.app.bq_client import BigQueryManager
import logging
from typing import Optional, List, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Instantiate MCP Server
mcp = FastMCP("bigquery-mcp-server")

# Instantiate BigQuery Manager
bq_manager = BigQueryManager()

@mcp.tool()
def create_dataset(dataset_id: str, location: str = "US") -> str:
    """
    Creates a new Google Cloud BigQuery dataset.
    
    Args:
        dataset_id (str): The ID of the dataset to create.
        location (str): The location for the dataset (e.g., 'US', 'EU'). Defaults to 'US'.
        
    Returns:
        str: Success message with the dataset ID.
    """
    logger.info(f"Tool call: create_dataset(dataset_id={dataset_id}, location={location})")
    full_id = bq_manager.create_dataset(dataset_id, location)
    return f"Successfully created dataset: {full_id}"

@mcp.tool()
def create_table(dataset_id: str, table_id: str, schema_json: List[Dict[str, str]]) -> str:
    """
    Creates a new table in BigQuery.
    
    Args:
        dataset_id (str): The ID of the dataset.
        table_id (str): The ID of the table to create.
        schema_json (List[Dict[str, str]]): A list of dictionaries defining the schema. 
                                            Example: [{"name": "id", "type": "INTEGER"}]
                                            
    Returns:
        str: Success message with the table ID.
    """
    logger.info(f"Tool call: create_table(dataset_id={dataset_id}, table_id={table_id})")
    full_id = bq_manager.create_table(dataset_id, table_id, schema_json)
    return f"Successfully created table: {full_id}"

@mcp.tool()
def get_table_schema(dataset_id: str, table_id: str) -> str:
    """
    Retrieves the schema definition of a specific table.
    
    Args:
        dataset_id (str): The ID of the dataset.
        table_id (str): The ID of the table.
        
    Returns:
        str: A JSON string representation of the schema.
    """
    logger.info(f"Tool call: get_table_schema(dataset_id={dataset_id}, table_id={table_id})")
    schema = bq_manager.get_table_schema(dataset_id, table_id)
    import json
    return json.dumps(schema, indent=2)

@mcp.tool()
def list_tables(dataset_id: str) -> str:
    """
    Retrieves a list of all tables within a given dataset.
    
    Args:
        dataset_id (str): The ID of the dataset.
        
    Returns:
        str: A comma-separated list of table IDs.
    """
    logger.info(f"Tool call: list_tables(dataset_id={dataset_id})")
    tables = bq_manager.list_tables(dataset_id)
    if not tables:
        return f"No tables found in dataset {dataset_id}."
    return f"Tables in {dataset_id}: " + ", ".join(tables)

@mcp.tool()
def add_row(dataset_id: str, table_id: str, row: Dict[str, Any]) -> str:
    """
    Inserts a single new row into an existing table.
    
    Args:
        dataset_id (str): The ID of the dataset.
        table_id (str): The ID of the table.
        row (Dict[str, Any]): A dictionary mapping column names to values.
        
    Returns:
        str: Success or failure message.
    """
    logger.info(f"Tool call: add_row(dataset_id={dataset_id}, table_id={table_id})")
    result = bq_manager.insert_rows(dataset_id, table_id, [row])
    import json
    return json.dumps(result)

@mcp.tool()
def execute_query(query: str) -> str:
    """
    Executes a read-only SQL query against BigQuery and safely returns the results.
    
    Args:
        query (str): The standard SQL query to execute. It's recommended to limit results (e.g., LIMIT 100).
        
    Returns:
        str: A JSON string of the result rows.
    """
    logger.info(f"Tool call: execute_query()")
    results = bq_manager.execute_query(query)
    import json
    return json.dumps(results, indent=2)
