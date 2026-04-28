from typing import Annotated, Optional
from pydantic import BaseModel, Field


class ImportGcsToArtifactRequest(BaseModel):
    """
    Request schema for importing a GCS object into the session artifacts.
    """

    gcs_uri: Annotated[
        str,
        Field(
            description="The canonical GCS URI of the object to import (e.g., gs://bucket/path/to/file.pdf).",
            pattern=r"^gs://[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]/.*$",
        ),
    ]
    artifact_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional name for the artifact in the session. If not provided, it will be derived from the GCS object name.",
        ),
    ]
    mime_type: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional MIME type of the object (e.g., application/pdf). If not provided, it will be guessed.",
        ),
    ]


class ImportGcsToArtifactResponse(BaseModel):
    """
    Response schema for the GCS-to-Artifact import tool.
    """

    artifact_id: Annotated[
        str,
        Field(
            description="The unique identifier of the created artifact in the session."
        ),
    ]
    gcs_uri: Annotated[str, Field(description="The source GCS URI.")]
    content_type: Annotated[
        Optional[str],
        Field(default=None, description="The MIME type of the imported object."),
    ]
    execution_status: Annotated[
        str, Field(description="Status of the operation (success/error).")
    ]
    execution_message: Annotated[
        str, Field(description="Human-readable message about the operation result.")
    ]


class GetArtifactUriRequest(BaseModel):
    """
    Request schema for retrieving a GCS URI for an artifact.
    """

    filename: Annotated[
        str,
        Field(
            description="The name of the artifact to retrieve the URI for (e.g., 'data.csv')."
        ),
    ]
    version: Annotated[
        Optional[int],
        Field(default=None, description="Optional specific version of the artifact."),
    ]


class GetArtifactUriResponse(BaseModel):
    """
    Response schema for the GetArtifactUri tool.
    """

    gcs_uri: Annotated[
        Optional[str], Field(description="The full GCS URI (gs://...) of the artifact.")
    ]
    execution_status: Annotated[str, Field(description="Status of the tool execution.")]
    execution_message: Annotated[
        str, Field(description="Human-readable message about the operation result.")
    ]
