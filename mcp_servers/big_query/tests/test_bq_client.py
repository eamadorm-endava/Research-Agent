import pytest
from unittest.mock import MagicMock, patch
from mcp_servers.big_query.app.bq_client import BigQueryManager
from google.cloud import bigquery

@patch('mcp_servers.big_query.app.bq_client.bigquery.Client')
def test_init_success(mock_client):
    manager = BigQueryManager()
    assert manager.client == mock_client()

@patch('mcp_servers.big_query.app.bq_client.bigquery.Client')
def test_create_dataset(mock_client):
    manager = BigQueryManager()
    manager.client.project = 'test-project'
    mock_dataset = MagicMock()
    mock_dataset.dataset_id = 'my_dataset'
    mock_dataset.full_dataset_id = 'test-project.my_dataset'
    manager.client.create_dataset.return_value = mock_dataset
    
    result = manager.create_dataset('my_dataset')
    assert result == 'test-project.my_dataset'
    manager.client.create_dataset.assert_called_once()

@patch('mcp_servers.big_query.app.bq_client.bigquery.SchemaField.from_api_repr')
@patch('mcp_servers.big_query.app.bq_client.bigquery.Table')
@patch('mcp_servers.big_query.app.bq_client.bigquery.Client')
def test_create_table(mock_client, mock_table, mock_schema_field):
    manager = BigQueryManager()
    manager.client.project = 'test-project'
    mock_table_instance = MagicMock()
    mock_table_instance.table_id = 'my_table'
    mock_table_instance.full_table_id = 'test-project.my_dataset.my_table'
    manager.client.create_table.return_value = mock_table_instance
    mock_table.return_value = mock_table_instance
    mock_schema_field.return_value = 'mock_schema_object'
    
    schema_json = [{"name": "id", "type": "INTEGER"}]
    result = manager.create_table('my_dataset', 'my_table', schema_json)
    
    assert result == 'test-project.my_dataset.my_table'
    mock_schema_field.assert_called_once_with({"name": "id", "type": "INTEGER"})
    mock_table.assert_called_once_with('test-project.my_dataset.my_table', schema=['mock_schema_object'])
    manager.client.create_table.assert_called_once_with(mock_table_instance, exists_ok=True)

@patch('mcp_servers.big_query.app.bq_client.bigquery.Client')
def test_get_table_schema(mock_client):
    manager = BigQueryManager()
    manager.client.project = 'test-project'
    
    mock_table = MagicMock()
    mock_field1 = MagicMock()
    mock_field1.to_api_repr.return_value = {"name": "id", "type": "INTEGER"}
    mock_field2 = MagicMock()
    mock_field2.to_api_repr.return_value = {"name": "name", "type": "STRING"}
    mock_table.schema = [mock_field1, mock_field2]
    
    manager.client.get_table.return_value = mock_table
    
    schema = manager.get_table_schema('my_dataset', 'my_table')
    
    assert schema == [{"name": "id", "type": "INTEGER"}, {"name": "name", "type": "STRING"}]
    manager.client.get_table.assert_called_once_with('test-project.my_dataset.my_table')


@patch('mcp_servers.big_query.app.bq_client.bigquery.Client')
def test_list_tables(mock_client):
    manager = BigQueryManager()
    
    table1 = MagicMock()
    table1.table_id = 'table_a'
    table2 = MagicMock()
    table2.table_id = 'table_b'
    
    manager.client.list_tables.return_value = [table1, table2]
    
    tables = manager.list_tables('my_dataset')
    
    assert tables == ['table_a', 'table_b']
    manager.client.list_tables.assert_called_with('my_dataset')

@patch('mcp_servers.big_query.app.bq_client.bigquery.Client')
def test_insert_rows_success(mock_client):
    manager = BigQueryManager()
    manager.client.project = 'test-project'
    
    manager.client.insert_rows_json.return_value = [] # Empty list means no errors
    
    rows = [{"name": "test", "age": 30}]
    result = manager.insert_rows('dataset', 'table', rows)
    
    assert result == {"status": "success", "inserted": 1}
    manager.client.insert_rows_json.assert_called_with('test-project.dataset.table', rows)

@patch('mcp_servers.big_query.app.bq_client.bigquery.Client')
def test_execute_query(mock_client):
    manager = BigQueryManager()
    mock_job = MagicMock()
    
    # Mock row returned by query
    mock_row = {'col1': 'val1', 'col2': 100}
    mock_job.result.return_value = [mock_row]
    
    manager.client.query.return_value = mock_job
    
    result = manager.execute_query('SELECT * FROM test-project.dataset.table')
    assert result == [mock_row]
    manager.client.query.assert_called_with('SELECT * FROM test-project.dataset.table')
