import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError
from mcp_servers.big_query.app.mcp_server import (
    create_dataset,
    create_table,
    get_table_schema,
    add_rows,
    execute_query,
    list_tables,
)
from mcp_servers.big_query.app.schemas import (
    CreateDatasetRequest,
    CreateTableRequest,
    GetTableSchemaRequest,
    AddRowsRequest,
    ExecuteQueryRequest,
    ListTablesRequest,
    AvailableProject,
)


@pytest.fixture
def mock_bq_manager():
    """
    Fixture that provides a mocked BigQueryManager.
    Implementation: Uses unittest.mock.patch to intercept the bq_manager instance in the mcp_server module.
    """
    manager = MagicMock()
    with patch(
        "mcp_servers.big_query.app.mcp_server._make_bq_manager",
        return_value=manager,
    ):
        yield manager


@pytest.mark.asyncio
async def test_mcp_create_dataset_success(mock_bq_manager):
    """
    Tests the successful execution of the create_dataset MCP tool.
    Implementation: Mocks the BigQueryManager's create_dataset response and verifies the ToolResponse contains a 'success' status and the correct message.
    """
    mock_bq_manager.create_dataset.return_value = (
        "projects/p-dev-gce-60pf/datasets/my_ds"
    )
    req = CreateDatasetRequest(
        project_id=AvailableProject.DEV, dataset_id="my_ds", location="US"
    )

    result = await create_dataset(req)

    assert result.execution_status == "success"
    assert "Successfully created dataset" in result.execution_message
    mock_bq_manager.create_dataset.assert_called_once_with(
        AvailableProject.DEV, "my_ds", "US"
    )


@pytest.mark.asyncio
async def test_mcp_create_dataset_validation_error():
    """
    Tests that the CreateDatasetRequest enforces strict Pydantic validation.
    Implementation: Attempts to instantiate the request model with invalid project IDs and malformed dataset IDs, asserting that Pydantic raises a ValidationError.
    """
    # Invalid Project ID (Literal/Enum violation)
    with pytest.raises(ValidationError):
        CreateDatasetRequest(project_id="invalid-proj", dataset_id="ds", location="US")

    # Invalid Dataset ID (Regex violation)
    with pytest.raises(ValidationError):
        CreateDatasetRequest(
            project_id=AvailableProject.DEV, dataset_id="ds@invalid", location="US"
        )


@pytest.mark.asyncio
async def test_mcp_execute_query_destructive_error():
    """
    Tests the security validation in ExecuteQueryRequest against destructive SQL commands.
    Implementation: Verifies that keywords like 'DROP' trigger a ValueError during model validation to prevent unauthorized schema mutations via read-only tools.
    """
    # SQL Injection / Destructive command prevention
    with pytest.raises(ValidationError) as exc:
        ExecuteQueryRequest(
            project_id=AvailableProject.DEV, query="DROP TABLE my_table"
        )
    assert "Destructive command 'DROP' detected" in str(exc.value)


@pytest.mark.asyncio
async def test_mcp_create_table_error_handling(mock_bq_manager):
    """
    Tests the MCP tool's error response when the underlying BigQuery operation fails.
    Implementation: Mocks an exception in the BigQueryManager and verifies that the tool returns an 'error' execution_status and includes the error details in the message.
    """
    mock_bq_manager.create_table.side_effect = Exception("BQ Error")
    req = CreateTableRequest(
        project_id=AvailableProject.DEV,
        dataset_id="ds",
        table_id="table",
        schema_fields=[{"name": "id", "type": "INT"}],
    )

    result = await create_table(req)

    assert result.execution_status == "error"
    assert "BQ Error" in result.execution_message


@pytest.mark.asyncio
async def test_mcp_get_table_schema_success(mock_bq_manager):
    """
    Tests the get_table_schema MCP tool with valid input.
    Implementation: Mocks the retrieval of table fields and verifies the tool correctly formats and returns the schema in the execution response.
    """
    mock_field = MagicMock()
    mock_field.to_api_repr.return_value = {"name": "id", "type": "INTEGER"}
    mock_bq_manager.get_table_schema.return_value = [mock_field]

    req = GetTableSchemaRequest(
        project_id=AvailableProject.DEV, dataset_id="ds", table_id="table"
    )
    result = await get_table_schema(req)

    assert result.execution_status == "success"
    assert result.fields == [{"name": "id", "type": "INTEGER"}]


@pytest.mark.asyncio
async def test_mcp_add_rows_success(mock_bq_manager):
    """
    Tests the add_rows MCP tool for successful data insertion.
    Implementation: Invokes the tool with a valid AddRowsRequest and confirms that BigQueryManager.insert_rows is called with the correct parameters, yielding a success response.
    """
    req = AddRowsRequest(
        project_id=AvailableProject.DEV,
        dataset_id="ds",
        table_id="table",
        rows=[{"id": 1}],
    )

    result = await add_rows(req)

    assert result.execution_status == "success"
    assert "Successfully inserted 1 rows" in result.execution_message
    mock_bq_manager.insert_rows.assert_called_once_with(
        AvailableProject.DEV, "ds", "table", [{"id": 1}]
    )


@pytest.mark.asyncio
async def test_mcp_execute_query_authorized_user_success(mock_bq_manager):
    """
    Simulates an authorized user successfully querying their allowed dataset.
    """
    mock_bq_manager.execute_query.return_value = [{"id": 1, "name": "allowed"}]
    req = ExecuteQueryRequest(
        project_id=AvailableProject.DEV,
        query="SELECT id, name FROM `p-dev-gce-60pf.ds.allowed_table` LIMIT 10",
    )

    result = await execute_query(req)

    assert result.execution_status == "success"
    assert result.results == [{"id": 1, "name": "allowed"}]


@pytest.mark.asyncio
async def test_mcp_list_tables_unauthorized_user_permission_denied(mock_bq_manager):
    """
    Simulates an unauthorized user getting a normalized permission denied error.
    """
    mock_bq_manager.list_tables.side_effect = Exception(
        "403 Access Denied: User does not have bigquery.tables.list permission"
    )
    req = ListTablesRequest(
        project_id=AvailableProject.DEV,
        dataset_id="restricted_ds",
    )

    result = await list_tables(req)

    assert result.execution_status == "error"
    assert "Permission Denied" in result.execution_message
