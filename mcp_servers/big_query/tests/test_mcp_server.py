import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError
from mcp_servers.big_query.app.mcp_server import (
    create_dataset,
    create_table,
    ekb_keyword_search,
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
    KeywordSearchRequest,
    ListTablesRequest,
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
        "projects/ag-core-ops-auj0/datasets/my_ds"
    )
    req = CreateDatasetRequest(dataset_id="my_ds", location="US")

    result = await create_dataset(req)

    assert result.execution_status == "success"
    assert "Successfully created dataset" in result.execution_message
    mock_bq_manager.create_dataset.assert_called_once_with(
        "mock-bq-project-id", "my_ds", "US"
    )


@pytest.mark.asyncio
async def test_mcp_create_dataset_validation_error():
    """
    Tests that the CreateDatasetRequest enforces strict Pydantic validation.
    Implementation: Attempts to instantiate the request model with invalid project IDs and malformed dataset IDs, asserting that Pydantic raises a ValidationError.
    """
    # Invalid Dataset ID
    with pytest.raises(ValidationError):
        CreateDatasetRequest(
            project_id="ag-core-ops-auj0", dataset_id="ds@invalid", location="US"
        )

    # Invalid Dataset ID (Regex violation)
    with pytest.raises(ValidationError):
        CreateDatasetRequest(
            project_id="ag-core-ops-auj0", dataset_id="ds@invalid", location="US"
        )


@pytest.mark.asyncio
async def test_mcp_execute_query_destructive_error():
    """
    Tests the security validation in ExecuteQueryRequest against destructive SQL commands.
    Implementation: Verifies that keywords like 'DROP' trigger a ValueError during model validation to prevent unauthorized schema mutations via read-only tools.
    """
    # SQL Injection / Destructive command prevention
    with pytest.raises(ValidationError) as exc:
        ExecuteQueryRequest(query="DROP TABLE my_table")
    assert "Destructive command 'DROP' detected" in str(exc.value)


@pytest.mark.asyncio
async def test_mcp_create_table_error_handling(mock_bq_manager):
    """
    Tests the MCP tool's error response when the underlying BigQuery operation fails.
    Implementation: Mocks an exception in the BigQueryManager and verifies that the tool returns an 'error' execution_status and includes the error details in the message.
    """
    mock_bq_manager.create_table.side_effect = Exception("BQ Error")
    req = CreateTableRequest(
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

    req = GetTableSchemaRequest(dataset_id="ds", table_id="table")
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
        dataset_id="ds",
        table_id="table",
        rows=[{"id": 1}],
    )

    result = await add_rows(req)

    assert result.execution_status == "success"
    assert "Successfully inserted 1 rows" in result.execution_message
    mock_bq_manager.insert_rows.assert_called_once_with(
        "mock-bq-project-id", "ds", "table", [{"id": 1}]
    )


@pytest.mark.asyncio
async def test_mcp_execute_query_authorized_user_success(mock_bq_manager):
    """
    Simulates an authorized user successfully querying their allowed dataset.
    """
    mock_bq_manager.execute_query.return_value = [{"id": 1, "name": "allowed"}]
    req = ExecuteQueryRequest(
        query="SELECT id, name FROM `ag-core-ops-auj0.ds.allowed_table` LIMIT 10",
    )

    result = await execute_query(req)

    assert result.execution_status == "success"
    assert result.results == [{"id": 1, "name": "allowed"}]


@pytest.mark.asyncio
async def test_mcp_ekb_keyword_search_success(mock_bq_manager):
    """
    Tests the successful execution of the ekb_keyword_search MCP tool.
    Implementation: Mocks keyword_search to return two distinct rows and verifies the tool
    returns a success status with the expected results list.
    """
    mock_bq_manager.keyword_search.return_value = [
        {
            "gcs_uri": "gs://bucket/report.pdf",
            "uploader_email": "user@example.com",
            "description": "Alpha project report",
            "filename": "report.pdf",
            "project_id": "Alpha Project",
        },
        {
            "gcs_uri": "gs://bucket/spec.pdf",
            "uploader_email": "other@example.com",
            "description": "Beta project spec",
            "filename": "spec.pdf",
            "project_id": "Beta Project",
        },
    ]
    req = KeywordSearchRequest(keyword="kubernetes")

    result = await ekb_keyword_search(req)

    assert result.execution_status == "success"
    assert len(result.results) == 2
    assert result.results[0]["filename"] == "report.pdf"
    mock_bq_manager.keyword_search.assert_called_once_with(req)


@pytest.mark.asyncio
async def test_mcp_ekb_keyword_search_empty_keyword_validation_error():
    """
    Tests that KeywordSearchRequest rejects an empty string keyword at schema validation time.
    Implementation: Attempts to instantiate the request with an empty keyword and asserts
    Pydantic raises a ValidationError before any tool execution occurs.
    """
    with pytest.raises(ValidationError):
        KeywordSearchRequest(keyword="")


@pytest.mark.asyncio
async def test_mcp_ekb_keyword_search_bq_error(mock_bq_manager):
    """
    Tests that ekb_keyword_search returns an error status when the underlying BQ call raises.
    Implementation: Configures keyword_search to raise a generic exception and verifies the
    tool wraps it in an error response rather than propagating the exception.
    """
    mock_bq_manager.keyword_search.side_effect = Exception("BQ failure")
    req = KeywordSearchRequest(keyword="react")

    result = await ekb_keyword_search(req)

    assert result.execution_status == "error"
    assert "BQ failure" in result.execution_message


@pytest.mark.asyncio
async def test_mcp_list_tables_unauthorized_user_permission_denied(mock_bq_manager):
    """
    Simulates an unauthorized user getting a normalized permission denied error.
    """
    mock_bq_manager.list_tables.side_effect = Exception(
        "403 Access Denied: User does not have bigquery.tables.list permission"
    )
    req = ListTablesRequest(
        dataset_id="restricted_ds",
    )

    result = await list_tables(req)

    assert result.execution_status == "error"
    assert "Permission Denied" in result.execution_message
