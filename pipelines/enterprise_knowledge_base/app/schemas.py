from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field
from enum import Enum


class JobStatus(str, Enum):
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


JobId = Annotated[str, Field(description="Unique identifier for the ingestion job")]


class OrchestratorRunRequest(BaseModel):
    """Request schema for the KB Orchestrator run method."""

    gcs_uri: Annotated[
        str,
        Field(
            description="The initial landing URI of the document",
            pattern=r"^gs://[a-z0-9_\-\.]+/.*$",
        ),
    ]

    @property
    def filename(self) -> str:
        """Extracts the filename from the GCS URI."""
        return self.gcs_uri.split("/")[-1]


class PipelineResult(BaseModel):
    """Schema for the internal results of the pipeline execution."""

    gcs_uri: Annotated[str, Field(description="The final GCS URI in the domain bucket")]
    chunks_generated: Annotated[int, Field(description="Number of chunks created")]
    final_domain: Annotated[str, Field(description="The determined business domain")]
    security_tier: Annotated[str, Field(description="The security tier label")]


class OrchestratorRunResponse(BaseModel):
    """Response schema for the initial async trigger."""

    job_id: JobId
    status: Annotated[JobStatus, Field(description="Current status of the job")]
    message: Annotated[str, Field(description="Informational message about the job")]


class JobStatusResponse(OrchestratorRunResponse):
    """Detailed response schema for status polling."""

    gcs_uri: Annotated[
        Optional[str], Field(description="The final GCS URI", default=None)
    ]
    chunks_generated: Annotated[
        Optional[int], Field(description="Number of chunks created", default=None)
    ]
    final_domain: Annotated[
        Optional[
            Literal["it", "finance", "hr", "sales", "executives", "legal", "operations"]
        ],
        Field(description="The determined business domain", default=None),
    ]
    security_tier: Annotated[
        Optional[str], Field(description="The security tier label", default=None)
    ]
