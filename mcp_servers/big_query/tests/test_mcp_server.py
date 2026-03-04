import pytest
import json
from unittest.mock import MagicMock, patch
from mcp_servers.big_query.app.mcp_server import (
    create_dataset,
    create_table,
    get_table_schema,
    list_tables,
    add_row,
    execute_query
)

@pytest.fixture
def mock_bq_manager():
    with patch('mcp_servers.big_query.app.mcp_server.bq_manager') as mock_manager:
        yield mock_manager

def test_mcp_create_dataset(mock_bq_manager):
    mock_bq_manager.create_dataset.return_value = 'test-project.my_dataset'
    
    result = create_dataset('my_dataset', 'EU')
    
    assert result == "Successfully created dataset: test-project.my_dataset"
    mock_bq_manager.create_dataset.assert_called_once_with('my_dataset', 'EU')

def test_mcp_create_dataset_default_location(mock_bq_manager):
    mock_bq_manager.create_dataset.return_value = 'test-project.my_dataset'
    
    result = create_dataset('my_dataset')
    
    assert result == "Successfully created dataset: test-project.my_dataset"
    mock_bq_manager.create_dataset.assert_called_once_with('my_dataset', 'US')

def test_mcp_create_table(mock_bq_manager):
    mock_bq_manager.create_table.return_value = 'test-project.my_dataset.my_table'
    schema_json = [{"name": "id", "type": "INTEGER"}]
    
    result = create_table('my_dataset', 'my_table', schema_json)
    
    assert result == "Successfully created table: test-project.my_dataset.my_table"
    mock_bq_manager.create_table.assert_called_once_with('my_dataset', 'my_table', schema_json)

def test_mcp_get_table_schema(mock_bq_manager):
    mock_schema = [{"name": "id", "type": "INTEGER"}]
    mock_bq_manager.get_table_schema.return_value = mock_schema
    
    result = get_table_schema('my_dataset', 'my_table')
    
    assert result == json.dumps(mock_schema, indent=2)
    mock_bq_manager.get_table_schema.assert_called_once_with('my_dataset', 'my_table')

def test_mcp_list_tables(mock_bq_manager):
    mock_bq_manager.list_tables.return_value = ['table_a', 'table_b']
    
    result = list_tables('my_dataset')
    
    assert result == "Tables in my_dataset: table_a, table_b"
    mock_bq_manager.list_tables.assert_called_once_with('my_dataset')

def test_mcp_list_tables_empty(mock_bq_manager):
    mock_bq_manager.list_tables.return_value = []
    
    result = list_tables('empty_dataset')
    
    assert result == "No tables found in dataset empty_dataset."
    mock_bq_manager.list_tables.assert_called_once_with('empty_dataset')

def test_mcp_add_row(mock_bq_manager):
    mock_result = {"status": "success", "inserted": 1}
    mock_bq_manager.insert_rows.return_value = mock_result
    
    row = {"id": 1, "name": "Test"}
    result = add_row('my_dataset', 'my_table', row)
    
    assert result == json.dumps(mock_result)
    mock_bq_manager.insert_rows.assert_called_once_with('my_dataset', 'my_table', [row])

def test_mcp_execute_query(mock_bq_manager):
    mock_results = [{"col1": "val1", "col2": 100}]
    mock_bq_manager.execute_query.return_value = mock_results
    
    query = "SELECT * FROM my_table LIMIT 1"
    result = execute_query(query)
    
    assert result == json.dumps(mock_results, indent=2)
    mock_bq_manager.execute_query.assert_called_once_with(query)
