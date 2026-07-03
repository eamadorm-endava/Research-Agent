from typing import Annotated

from pydantic import BaseModel, Field

from ..schemas import MetricsRecord


class InsertMetricsRequest(BaseModel):
    """Request schema for inserting metrics into BigQuery."""

    record: Annotated[MetricsRecord, Field(description="The metrics record to insert")]


class InsertMetricsResponse(BaseModel):
    """Response schema for BigQuery insertion."""

    success: Annotated[bool, Field(description="Whether the insertion was successful")]
    error_message: Annotated[
        str | None,
        Field(description="Error message if insertion failed", default=None),
    ]
