import asyncio
import sys
import os

# Ensure the root of the repository is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from mcp_servers.big_query.app.mcp_server import mcp
from mcp_servers.big_query.app.bq_client import BigQueryManager
import logging

logging.basicConfig(level=logging.INFO)

async def test_bigquery():
    print("🚀 Initializing BigQuery MCP Server tools locally...")
    
    # Initialize the client (Uses ADC automatically)
    bq_manager = BigQueryManager()
    
    # Configure your test environment here:
    TEST_DATASET = "mcp_test_dataset"
    TEST_TABLE = "users"
    
    print("\n--- 1. Testing Dataset Creation ---")
    dataset_res = bq_manager.create_dataset(TEST_DATASET)
    print(f"Result: {dataset_res}")
    
    print("\n--- 2. Testing Table Creation ---")
    schema = [
        {"name": "id", "type": "INTEGER"},
        {"name": "name", "type": "STRING"},
        {"name": "age", "type": "INTEGER"}
    ]
    table_res = bq_manager.create_table(TEST_DATASET, TEST_TABLE, schema)
    print(f"Result: {table_res}")
    
    print("\n--- 3. Testing Schema Retrieval ---")
    schema_res = bq_manager.get_table_schema(TEST_DATASET, TEST_TABLE)
    print(f"Result: {schema_res}")
    
    print("\n--- 4. Testing Insert Rows ---")
    rows = [
        {"id": 1, "name": "Alice", "age": 30},
        {"id": 2, "name": "Bob", "age": 25}
    ]
    insert_res = bq_manager.insert_rows(TEST_DATASET, TEST_TABLE, rows)
    print(f"Result: {insert_res}")
    
    # Wait briefly for streaming buffer
    print("Waiting a few seconds for data to become available...")
    await asyncio.sleep(5)
    
    print("\n--- 5. Testing Query Execution ---")
    query = f"SELECT * FROM `{bq_manager.client.project}.{TEST_DATASET}.{TEST_TABLE}` LIMIT 10"
    query_res = bq_manager.execute_query(query)
    print(f"Result: {query_res}")
    
    print("\n✅ Verification complete! (Don't forget to delete the test dataset in GCP Console)")

if __name__ == "__main__":
    asyncio.run(test_bigquery())
