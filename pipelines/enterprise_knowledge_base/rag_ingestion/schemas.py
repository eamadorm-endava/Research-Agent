from typing import Annotated, Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Schema for a single document chunk stored in BigQuery."""

    chunk_id: Annotated[str, Field(description="Unique UUID for the chunk")]
    document_id: Annotated[
        str, Field(description="Deterministic UUID for the document")
    ]
    chunk_data: Annotated[str, Field(description="Text content of the chunk")]
    gcs_uri: Annotated[str, Field(description="Original GCS URI of the document")]
    filename: Annotated[str, Field(description="Basename of the file")]
    structural_metadata: Annotated[
        str, Field(description="JSON string with page info, etc.")
    ]
    page_number: Annotated[
        int, Field(description="Page number where the chunk was found")
    ]
    embedding: Annotated[
        list[float],
        Field(description="Vector embedding (empty initially)", default_factory=list),
    ]
    created_at: Annotated[str, Field(description="ISO timestamp of creation")]
    vectorized_at: Annotated[
        Optional[str], Field(description="ISO timestamp of vectorization", default=None)
    ]


class IngestDocumentRequest(BaseModel):
    """Request schema for ingesting a document."""

    gcs_uri: Annotated[str, Field(description="GCS URI of the PDF to ingest")]


class IngestDocumentResponse(BaseModel):
    """Response schema for document ingestion."""

    chunk_count: Annotated[
        int, Field(description="Number of chunks successfully staged")
    ]
    processed_uri: Annotated[
        str, Field(description="The new GCS URI of the processed document")
    ]
    execution_status: Annotated[
        str, Field(description="Status message of the operation")
    ]


class GenerateEmbeddingsRequest(BaseModel):
    """Request schema for generating embeddings."""

    gcs_uri: Annotated[str, Field(description="GCS URI of the document to vectorize")]


class GenerateEmbeddingsResponse(BaseModel):
    """Response schema for embedding generation."""

    success: Annotated[
        bool, Field(description="Whether the vectorization job completed")
    ]
    execution_status: Annotated[
        str, Field(description="Status message or error description")
    ]
