import asyncio
import logging
import re
from typing import Optional

import httpx
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .bq_client import BigQueryManager, build_bq_credentials
from .config import BIGQUERY_AUTH_CONFIG, BIGQUERY_SERVER_CONFIG
from .schemas import (
    AuthenticationError,
    GetTableSchemaRequest,
    GetTableSchemaResponse,
    CreateDatasetRequest,
    CreateDatasetResponse,
    ListDatasetsRequest,
    ListDatasetsResponse,
    CreateTableRequest,
    CreateTableResponse,
    ListTablesRequest,
    ListTablesResponse,
    AddRowsRequest,
    AddRowsResponse,
    ExecuteQueryRequest,
    ExecuteQueryResponse,
)

# Configure logging
logger = logging.getLogger(__name__)


class GoogleBigQueryTokenVerifier(TokenVerifier):
    """Verifies a Google OAuth access token against Google's tokeninfo endpoint."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    BIGQUERY_AUTH_CONFIG.google_token_info_url,
                    params={"access_token": token},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return AccessToken(
                        token=token,
                        client_id=data.get("aud", "unknown"),
                        scopes=data.get("scope", "").split(),
                    )
        except Exception:
            pass
        return None


# Instantiate MCP Server
mcp = FastMCP(
    BIGQUERY_SERVER_CONFIG.server_name,
    stateless_http=BIGQUERY_SERVER_CONFIG.stateless_http,
    json_response=BIGQUERY_SERVER_CONFIG.json_response,
    host=BIGQUERY_SERVER_CONFIG.default_host,
    port=BIGQUERY_SERVER_CONFIG.default_port,
    debug=BIGQUERY_SERVER_CONFIG.debug,
    token_verifier=GoogleBigQueryTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(BIGQUERY_AUTH_CONFIG.google_accounts_issuer_url),
        resource_server_url=AnyHttpUrl(
            f"http://{BIGQUERY_SERVER_CONFIG.default_host}:{BIGQUERY_SERVER_CONFIG.default_port}"
        ),
    ),
)


@mcp.tool()
async def create_dataset(request: CreateDatasetRequest) -> CreateDatasetResponse:
    """
    Creates a new Google Cloud BigQuery dataset.
    Args:
        request (CreateDatasetRequest): Structured request containing project_id, dataset_id, and location.
    Returns:
        CreateDatasetResponse: Full request details and status.
    """
    logger.info(
        f"Tool call: create_dataset(project_id={request.project_id}, dataset_id={request.dataset_id})"
    )
    try:
        bq_manager = _make_bq_manager()
        full_id = await asyncio.to_thread(
            bq_manager.create_dataset,
            request.project_id,
            request.dataset_id,
            request.location,
        )
        return CreateDatasetResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            location=request.location,
            execution_status="success",
            execution_message=f"Successfully created dataset: {full_id}",
        )
    except AuthenticationError as e:
        return CreateDatasetResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            location=request.location,
            execution_status="error",
            execution_message=f"Authentication Error: {e}",
        )
    except Exception as e:
        return CreateDatasetResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            location=request.location,
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def list_datasets(request: ListDatasetsRequest) -> ListDatasetsResponse:
    """
    Lists all datasets in a BigQuery project.
    Args:
        request (ListDatasetsRequest): Structured request containing the project_id.
    Returns:
        ListDatasetsResponse: A List[str] containing dataset IDs.
    """
    logger.info(f"Tool call: list_datasets(project_id={request.project_id})")
    try:
        bq_manager = _make_bq_manager()
        datasets = await asyncio.to_thread(bq_manager.list_datasets, request.project_id)
        return ListDatasetsResponse(
            project_id=request.project_id,
            datasets=datasets,
            execution_status="success",
            execution_message=f"Found {len(datasets)} datasets in project {request.project_id}.",
        )
    except AuthenticationError as e:
        return ListDatasetsResponse(
            project_id=request.project_id,
            datasets=[],
            execution_status="error",
            execution_message=f"Authentication Error: {e}",
        )
    except Exception as e:
        return ListDatasetsResponse(
            project_id=request.project_id,
            datasets=[],
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def create_table(request: CreateTableRequest) -> CreateTableResponse:
    """
    Creates a new table in BigQuery.
    Args:
        request (CreateTableRequest): Structured request containing project_id, dataset_id, table_id, and schema_fields.
    Returns:
        CreateTableResponse: Full request details and status.
    """
    logger.info(
        f"Tool call: create_table(project_id={request.project_id}, dataset_id={request.dataset_id}, table_id={request.table_id})"
    )
    try:
        bq_manager = _make_bq_manager()
        full_id = await asyncio.to_thread(
            bq_manager.create_table,
            request.project_id,
            request.dataset_id,
            request.table_id,
            request.schema_fields,
        )
        return CreateTableResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            schema_fields=request.schema_fields,
            execution_status="success",
            execution_message=f"Successfully created table: {full_id}",
        )
    except AuthenticationError as e:
        return CreateTableResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            schema_fields=request.schema_fields,
            execution_status="error",
            execution_message=f"Authentication Error: {e}",
        )
    except Exception as e:
        return CreateTableResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            schema_fields=request.schema_fields,
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def get_table_schema(request: GetTableSchemaRequest) -> GetTableSchemaResponse:
    """
    Retrieves the schema definition of a specific table.
    Args:
        request (GetTableSchemaRequest): Structured request containing project_id, dataset_id, and table_id.
    Returns:
        GetTableSchemaResponse: The schema fields as a List[Dict[str, Any]].
    """
    logger.info(
        f"Tool call: get_table_schema(project_id={request.project_id}, dataset_id={request.dataset_id}, table_id={request.table_id})"
    )
    try:
        bq_manager = _make_bq_manager()
        schema_fields = await asyncio.to_thread(
            bq_manager.get_table_schema,
            request.project_id,
            request.dataset_id,
            request.table_id,
        )
        return GetTableSchemaResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            fields=[field.to_api_repr() for field in schema_fields],
            execution_status="success",
            execution_message=f"Schema retrieved for table {request.table_id}.",
        )
    except AuthenticationError as e:
        return GetTableSchemaResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            fields=[],
            execution_status="error",
            execution_message=f"Authentication Error: {e}",
        )
    except Exception as e:
        return GetTableSchemaResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            fields=[],
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def list_tables(request: ListTablesRequest) -> ListTablesResponse:
    """
    Retrieves a list of all tables within a given dataset.
    Args:
        request (ListTablesRequest): Structured request containing project_id and dataset_id.
    Returns:
        ListTablesResponse: A List[str] of table IDs.
    """
    logger.info(
        f"Tool call: list_tables(project_id={request.project_id}, dataset_id={request.dataset_id})"
    )
    try:
        bq_manager = _make_bq_manager()
        tables = await asyncio.to_thread(
            bq_manager.list_tables, request.project_id, request.dataset_id
        )
        return ListTablesResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            tables=tables,
            execution_status="success",
            execution_message=f"Found {len(tables)} tables in dataset {request.dataset_id}.",
        )
    except AuthenticationError as e:
        return ListTablesResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            tables=[],
            execution_status="error",
            execution_message=f"Authentication Error: {e}",
        )
    except Exception as e:
        return ListTablesResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            tables=[],
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def add_rows(request: AddRowsRequest) -> AddRowsResponse:
    """
    Inserts one or more rows into an existing table.
    Args:
        request (AddRowsRequest): Structured request containing project_id, dataset_id, table_id, and rows.
    Returns:
        AddRowsResponse: Full request details and status.
    """
    logger.info(
        f"Tool call: add_rows(project_id={request.project_id}, dataset_id={request.dataset_id}, table_id={request.table_id})"
    )
    try:
        bq_manager = _make_bq_manager()
        await asyncio.to_thread(
            bq_manager.insert_rows,
            request.project_id,
            request.dataset_id,
            request.table_id,
            request.rows,
        )
        return AddRowsResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            rows=request.rows,
            execution_status="success",
            execution_message=f"Successfully inserted {len(request.rows)} rows into table {request.table_id}.",
        )
    except AuthenticationError as e:
        return AddRowsResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            rows=request.rows,
            execution_status="error",
            execution_message=f"Authentication Error: {e}",
        )
    except Exception as e:
        return AddRowsResponse(
            project_id=request.project_id,
            dataset_id=request.dataset_id,
            table_id=request.table_id,
            rows=request.rows,
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def execute_query(request: ExecuteQueryRequest) -> ExecuteQueryResponse:
    """
    Executes a read-only SQL query against BigQuery.
    Args:
        request (ExecuteQueryRequest): Structured request containing project_id and query.
    Returns:
        ExecuteQueryResponse: The query results as a List[Dict[str, Any]].
    """
    logger.info(f"Tool call: execute_query(project_id={request.project_id})")
    try:
        bq_manager = _make_bq_manager()
        results = await asyncio.to_thread(
            bq_manager.execute_query, request.project_id, request.query
        )
        return ExecuteQueryResponse(
            project_id=request.project_id,
            query=request.query,
            results=results,
            execution_status="success",
            execution_message=f"Query executed successfully, returned {len(results)} rows.",
        )
    except AuthenticationError as e:
        return ExecuteQueryResponse(
            project_id=request.project_id,
            query=request.query,
            results=[],
            execution_status="error",
            execution_message=f"Authentication Error: {e}",
        )
    except Exception as e:
        return ExecuteQueryResponse(
            project_id=request.project_id,
            query=request.query,
            results=[],
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


def _make_bq_manager() -> BigQueryManager:
    """Creates a BigQuery manager using the delegated user token from MCP context."""
    access_token = _get_current_token()
    creds = build_bq_credentials(access_token=access_token)
    return BigQueryManager(creds)


def _get_current_token() -> Optional[str]:
    """Returns the currently authenticated OAuth access token from MCP auth context."""
    token_obj = get_access_token()
    return token_obj.token if token_obj else None


def _format_execution_error(exc: Exception) -> str:
    """Returns a sanitized, user-facing execution message with permission normalization."""
    raw_message = _sanitize_sensitive_text(str(exc))
    lowered = raw_message.lower()
    permission_markers = (
        "permission denied",
        "access denied",
        "insufficient permission",
        "insufficient permissions",
        "not authorized",
        "forbidden",
        "403",
    )
    if any(marker in lowered for marker in permission_markers):
        return f"Permission Denied: {raw_message}"
    return raw_message


def _sanitize_sensitive_text(value: str) -> str:
    """Redacts common credential fragments from error messages before returning them."""
    sanitized = value or ""
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9._\-~+/]+=*", "Bearer [REDACTED]", sanitized
    )
    sanitized = re.sub(r"ya29\.[A-Za-z0-9._\-~+/]+=*", "ya29.[REDACTED]", sanitized)
    sanitized = re.sub(r"access_token=[^&\s]+", "access_token=[REDACTED]", sanitized)
    return sanitized
