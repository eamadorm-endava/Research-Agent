from typing import Annotated, Literal
from pydantic import BaseModel, Field


class OrchestratorRunRequest(BaseModel):
    """Request schema for the KB Orchestrator run method."""

    gcs_uri: Annotated[
        str, Field(description="The initial landing URI of the document")
    ]


class OrchestratorRunResponse(BaseModel):
    """Response schema for the KB Orchestrator run method."""

    gcs_uri: Annotated[
        str, Field(description="The final unmasked GCS URI of the document")
    ]
    chunks_generated: Annotated[
        int, Field(description="Number of chunks vectorized and stored")
    ]
    final_domain: Annotated[
        Literal["it", "finance", "hr", "sales", "executives", "legal", "operations"],
        Field(description="The determined business domain"),
    ]
    security_tier: Annotated[
        str,
        Field(description="The string label of the security tier (e.g., confidential)"),
    ]
