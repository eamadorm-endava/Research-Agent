from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class UploadRequest(BaseModel):
    filename: str
    content_type: str


@router.post("/generate-url")
async def generate_signed_url(request: UploadRequest):
    """
    Generates a V4 GCS Signed URL for direct client-side uploads.
    To be implemented when dealing with file ingestion.
    """
    # TODO: Implement GCS Signed URL generation
    return {
        "url": "https://storage.googleapis.com/mock-signed-url",
        "gcs_uri": "gs://bucket/path/to/file",
    }
