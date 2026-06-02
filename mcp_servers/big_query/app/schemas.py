from typing import List, Dict, Any, Annotated, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re


# Reusable Types
DATASET_ID = Annotated[
    str,
    Field(
        description="The ID of the dataset.",
        pattern=r"^[\w-]+$",
        min_length=1,
        max_length=1024,
    ),
]
TABLE_ID = Annotated[
    str,
    Field(
        description="The ID of the table.",
        pattern=r"^[\w-]+$",
        min_length=1,
        max_length=1024,
    ),
]
LOCATION = Annotated[str, Field(default="US", description="The geographic location.")]
QUERY = Annotated[
    str, Field(description="The standard SQL query to execute.", min_length=1)
]
# Type for schema structures (definitions)
SCHEMA_DEFINITION = Annotated[
    List[Dict[str, Any]],
    Field(
        description="A list of dictionaries defining the schema, e.g., [{'name': 'id', 'type': 'INTEGER'}]."
    ),
]
# Type for data rows (both input for insertion and output for query results)
ROWS = Annotated[
    List[Dict[str, Any]],
    Field(
        description="A list of dictionaries representing data rows, where each dict is a mapping of column names to values."
    ),
]


class BaseResponse(BaseModel):
    """
    Base response model for all BigQuery tools.
    """

    execution_status: Annotated[
        Literal["success", "error"], Field(description="The status of the execution.")
    ]
    execution_message: Annotated[
        str,
        Field(
            default="Execution completed successfully.",
            description="Detailed message about the execution or error description.",
        ),
    ]


class AuthenticationError(Exception):
    """Raised when delegated OAuth authentication fails."""


class GetTableSchemaRequest(BaseModel):
    """
    Request model for retrieving table schema.
    """

    dataset_id: DATASET_ID
    table_id: TABLE_ID


class GetTableSchemaResponse(GetTableSchemaRequest, BaseResponse):
    """
    Response model for table schema retrieval.
    """

    fields: SCHEMA_DEFINITION


class CreateDatasetRequest(BaseModel):
    """
    Request model for creating a dataset.
    """

    dataset_id: DATASET_ID
    location: LOCATION


class CreateDatasetResponse(CreateDatasetRequest, BaseResponse):
    """
    Response model for dataset creation.
    """

    # No extra fields required
    pass


class ListDatasetsRequest(BaseModel):
    """
    Request model for listing datasets.
    """


class ListDatasetsResponse(ListDatasetsRequest, BaseResponse):
    """
    Response model for listing datasets.
    """

    datasets: Annotated[List[str], Field(description="A list of dataset ID strings.")]


class CreateTableRequest(BaseModel):
    """
    Request model for creating a table.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataset_id: DATASET_ID
    table_id: TABLE_ID
    schema_fields: SCHEMA_DEFINITION


class CreateTableResponse(CreateTableRequest, BaseResponse):
    """
    Response model for table creation.
    """

    # No extra fields required
    pass


class ListTablesRequest(BaseModel):
    """
    Request model for listing tables.
    """

    dataset_id: DATASET_ID


class ListTablesResponse(ListTablesRequest, BaseResponse):
    """
    Response model for listing tables.
    """

    tables: Annotated[List[str], Field(description="A list of table ID strings.")]


class AddRowsRequest(BaseModel):
    """
    Request model for inserting rows into a table.
    """

    dataset_id: DATASET_ID
    table_id: TABLE_ID
    rows: ROWS


class AddRowsResponse(AddRowsRequest, BaseResponse):
    """
    Response model for row insertion.
    """

    # No extra fields required
    pass


class ExecuteQueryRequest(BaseModel):
    """
    Request model for executing a SQL query.
    """

    query: QUERY

    @field_validator("query")
    @classmethod
    def check_read_only(cls, v: str) -> str:
        destructive_keywords = ["DROP", "DELETE", "TRUNCATE"]
        for keyword in destructive_keywords:
            if re.search(rf"\b{keyword}\b", v, re.IGNORECASE):
                raise ValueError(
                    f"This tool only support read-only queries. Destructive command '{keyword}' detected."
                )
        return v


class ExecuteQueryResponse(ExecuteQueryRequest, BaseResponse):
    """
    Response model for SQL query execution.
    """

    results: ROWS


class SemanticSearchRequest(BaseModel):
    """
    Request model for performing a semantic search against the knowledge base.
    """

    query: Annotated[
        str, Field(description="The natural language query to search for.")
    ]
    top_k: Annotated[
        int,
        Field(description="The number of results to return.", default=10, ge=1, le=50),
    ]
    filename: Annotated[
        Optional[str], Field(description="Filter by filename.", default=None)
    ]
    project_filter: Annotated[
        Optional[str],
        Field(description="Filter by project_id in metadata.", default=None),
    ]
    domain: Annotated[
        Optional[str], Field(description="Filter by business domain.", default=None)
    ]
    trust_level: Annotated[
        Optional[str],
        Field(description="Filter by trust maturity level.", default=None),
    ]


class SemanticSearchResponse(BaseResponse):
    """
    Response model for semantic search.
    """

    results: ROWS


class KeywordSearchRequest(BaseModel):
    """
    Request model for a deterministic keyword search against knowledge base chunks.
    """

    keyword: Annotated[
        str,
        Field(
            description="Single keyword to search for using case-insensitive matching.",
            min_length=1,
            max_length=200,
        ),
    ]


class KeywordSearchResponse(BaseResponse):
    """
    Response model for keyword search returning distinct filenames and project names.
    """

    results: ROWS
