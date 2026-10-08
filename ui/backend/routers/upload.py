"""Generate bounded, user-isolated upload URLs using ADC IAM signing."""

import hashlib
import uuid
from datetime import timedelta
from pathlib import PurePosixPath

import google.auth
from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport.requests import Request
from google.cloud import storage
from pydantic import BaseModel, Field, field_validator

from ..auth import get_current_user
from ..config import UI_CONFIG

router = APIRouter()
ALLOWED_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class UploadRequest(BaseModel):
    """Accept a filename, supported media type and a bounded byte count."""

    filename: str = Field(min_length=1, max_length=200)
    content_type: str
    size_bytes: int = Field(gt=0)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, filename: str) -> str:
        if PurePosixPath(filename).name != filename or "\\" in filename:
            raise ValueError("Filename must not contain path components")
        if any(ord(character) < 32 for character in filename):
            raise ValueError("Filename contains control characters")
        return filename


@router.post("/generate-url")
def generate_signed_url(body: UploadRequest, user_id: str = Depends(get_current_user)):
    """Sign one short-lived PUT with an exact content length and isolated object key."""
    if body.size_bytes > UI_CONFIG.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large")
    if body.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Unsupported file type")
    if not UI_CONFIG.LANDING_ZONE_BUCKET or not UI_CONFIG.SERVICE_ACCOUNT_EMAIL:
        raise HTTPException(503, "Upload storage is not configured")
    owner = hashlib.sha256(user_id.encode()).hexdigest()
    object_name = f"uploads/{owner}/{uuid.uuid4().hex}/{body.filename}"
    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(Request())
        blob = (
            storage.Client(project=UI_CONFIG.PROJECT_ID, credentials=credentials)
            .bucket(UI_CONFIG.LANDING_ZONE_BUCKET)
            .blob(object_name)
        )
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=5),
            method="PUT",
            content_type=body.content_type,
            headers={"Content-Length": str(body.size_bytes)},
            service_account_email=UI_CONFIG.SERVICE_ACCOUNT_EMAIL,
            access_token=credentials.token,
        )
    except Exception:  # noqa: BLE001 - API/UI boundary must not disclose credentials
        raise HTTPException(503, "Upload signing is unavailable") from None
    return {
        "url": url,
        "gcs_uri": f"gs://{UI_CONFIG.LANDING_ZONE_BUCKET}/{object_name}",
    }
