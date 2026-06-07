from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field


class GetArtifactURIRequest(BaseModel):
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


class GetArtifactURIResponse(BaseModel):
    """
    Response schema for the GetArtifactUri tool.
    """

    gcs_uri: Annotated[
        Optional[str],
        Field(default=None, description="The full GCS URI (gs://...) of the artifact."),
    ]
    execution_status: Annotated[Literal["success", "error"], Field(description="Status of the tool execution.")]
    execution_message: Annotated[
        str, Field(description="Human-readable message about the operation result.")
    ]
