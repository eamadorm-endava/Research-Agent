from unittest.mock import MagicMock, patch
import pytest
from mcp_servers.big_query.app.bq_client import BigQueryManager, build_bq_credentials
from mcp_servers.big_query.app.config import BIGQUERY_API_CONFIG


@pytest.fixture
def mock_client():
    """
    Fixture that provides a mocked BigQuery client.
    Implemented using unittest.mock.patch to replace the google.cloud.bigquery.Client.
    """
    with patch("mcp_servers.big_query.app.bq_client.bigquery.Client") as mock:
        yield mock


def test_init_success(mock_client):
    """
    Tests the successful initialization of the BigQueryManager.
    Implementation: Verifies that the internal client is correctly assigned to the mocked BigQuery client.
    """
    creds = MagicMock()
    manager = BigQueryManager(creds=creds)
    assert manager.client == mock_client.return_value
    mock_client.assert_called_once_with(credentials=creds, project=None)


def test_create_dataset(mock_client):
    """
    Tests the creation of a BigQuery dataset.
    Implementation: Mocks the client's create_dataset method and verifies it is called with the expected arguments, returning the dataset reference.
    """
    manager = BigQueryManager(creds=MagicMock())
    mock_dataset = MagicMock()
    mock_dataset.reference = "test-project.my_dataset"
    manager.client.create_dataset.return_value = mock_dataset

    result = manager.create_dataset("test-project", "my_dataset", "US")
    assert result == "test-project.my_dataset"
    manager.client.create_dataset.assert_called_once()


def test_list_datasets(mock_client):
    """
    Tests listing datasets in a BigQuery project.
    Implementation: Mocks the client's list_datasets method to return a list of mock datasets and verifies the returned IDs match the expectation.
    """
    manager = BigQueryManager(creds=MagicMock())
    mock_dataset1 = MagicMock()
    mock_dataset1.dataset_id = "ds1"
    mock_dataset2 = MagicMock()
    mock_dataset2.dataset_id = "ds2"
    manager.client.list_datasets.return_value = [mock_dataset1, mock_dataset2]

    result = manager.list_datasets("test-project")
    assert result == ["ds1", "ds2"]
    manager.client.list_datasets.assert_called_once_with(project="test-project")


@patch("mcp_servers.big_query.app.bq_client.bigquery.SchemaField.from_api_repr")
@patch("mcp_servers.big_query.app.bq_client.bigquery.Table")
def test_create_table(mock_table, mock_schema_field, mock_client):
    """
    Tests the creation of a BigQuery table with a specified schema.
    Implementation: Mocks SchemaField and Table creation, verifies specific API representations are processed and the client's create_table is invoked correctly.
    """
    manager = BigQueryManager(creds=MagicMock())
    mock_table_instance = MagicMock()
    mock_table_instance.reference = "test-project.my_dataset.my_table"
    manager.client.create_table.return_value = mock_table_instance
    mock_table.return_value = mock_table_instance
    mock_schema_field.return_value = "mock_schema_object"

    schema_json = [{"name": "id", "type": "INTEGER"}]
    result = manager.create_table("test-project", "my_dataset", "my_table", schema_json)

    assert result == "test-project.my_dataset.my_table"
    mock_schema_field.assert_called_once_with({"name": "id", "type": "INTEGER"})
    mock_table.assert_called_once_with(
        "test-project.my_dataset.my_table", schema=["mock_schema_object"]
    )


def test_get_table_schema(mock_client):
    """
    Tests the retrieval of a table's schema fields.
    Implementation: Mocks the client's get_table method to return a table with mock schema fields and verifies the schema is retrieved accurately.
    """
    manager = BigQueryManager(creds=MagicMock())

    mock_table = MagicMock()
    mock_field1 = MagicMock()
    mock_table.schema = [mock_field1]
    manager.client.get_table.return_value = mock_table

    # Mock table_exists to return True
    with patch.object(BigQueryManager, "table_exists", return_value=True):
        schema = manager.get_table_schema("test-project", "my_dataset", "my_table")
        assert schema == [mock_field1]
        manager.client.get_table.assert_called_once_with(
            "test-project.my_dataset.my_table"
        )


def test_list_tables(mock_client):
    """
    Tests listing all tables within a specific dataset.
    Implementation: Mocks the client's list_tables method and verifies that the resulting list of table IDs matches the mocked data.
    """
    manager = BigQueryManager(creds=MagicMock())
    table1 = MagicMock()
    table1.table_id = "table_a"
    manager.client.list_tables.return_value = [table1]

    tables = manager.list_tables("test-project", "my_dataset")
    assert tables == ["table_a"]
    manager.client.list_tables.assert_called_with("test-project.my_dataset")


def test_insert_rows_schema_preservation(mock_client):
    """
    Tests that a row insertion job correctly preserves the table's existing schema.
    Implementation: Checks that get_table_schema is called before insertion and its output is passed to the LoadJobConfig to prevent field mode resets.
    """
    manager = BigQueryManager(creds=MagicMock())

    # Mock dependencies
    with (
        patch.object(manager, "table_exists", return_value=True),
        patch.object(manager, "get_table_schema", return_value=["mock_schema"]),
        patch("google.cloud.bigquery.LoadJobConfig") as mock_config,
        patch("google.cloud.bigquery.SourceFormat.NEWLINE_DELIMITED_JSON", "NDJSON"),
    ):
        mock_job = MagicMock()
        manager.client.load_table_from_json.return_value = mock_job

        rows = [{"a": 1}]
        manager.insert_rows("test-project", "dataset", "table", rows)

        # Verify schema was fetched and passed to config
        manager.get_table_schema.assert_called_once_with(
            "test-project", "dataset", "table"
        )
        mock_config.assert_called_once_with(
            source_format="NDJSON", schema=["mock_schema"]
        )
        manager.client.load_table_from_json.assert_called_once()


def test_execute_query(mock_client):
    """
    Tests the execution of a SQL query and result retrieval.
    Implementation: Mocks the query job and verifies the result list of dictionaries matches the expected rows.
    """
    manager = BigQueryManager(creds=MagicMock())
    mock_job = MagicMock()
    mock_row = {"col1": "val1"}
    mock_job.result.return_value = [mock_row]
    manager.client.query.return_value = mock_job

    result = manager.execute_query("test-project", "SELECT 1")
    assert result == [{"col1": "val1"}]
    manager.client.query.assert_called_with("SELECT 1", project="test-project")


@patch("mcp_servers.big_query.app.bq_client.validate_access_token")
@patch("mcp_servers.big_query.app.bq_client.Credentials")
def test_build_bq_credentials_from_access_token(mock_credentials, mock_validate):
    access_token = "ya29.mock-token"

    build_bq_credentials(access_token=access_token)

    expected_scopes = list(BIGQUERY_API_CONFIG.read_write_scopes)

    mock_validate.assert_called_once_with(access_token, expected_scopes)
    mock_credentials.assert_called_once_with(
        token=access_token,
        scopes=expected_scopes,
    )
