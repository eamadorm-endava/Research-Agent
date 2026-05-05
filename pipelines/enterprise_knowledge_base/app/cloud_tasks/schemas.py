from pydantic import BaseModel, Field
from typing import Annotated

from ..schemas import JobIdType, OrchestratorRunRequest


class TaskPayload(BaseModel):
    """Schema for the payload pushed by Cloud Tasks."""

    job_id: JobIdType
    request: Annotated[
        OrchestratorRunRequest,
        Field(
            description="The original payload containing file metadata for ingestion."
        ),
    ]
