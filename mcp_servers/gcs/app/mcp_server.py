import asyncio
import re
from typing import Optional

import httpx
from loguru import logger
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .config import GCS_API_CONFIG, GCS_AUTH_CONFIG, GCS_SERVER_CONFIG
from .gcs_client import GCSManager, build_gcs_credentials, build_sa_credentials
from .schemas import (
    CreateBucketRequest,
    CreateBucketResponse,
    UpdateBucketLabelsRequest,
    UpdateBucketLabelsResponse,
    UploadObjectRequest,
    UploadObjectResponse,
    ReadObjectRequest,
    ReadObjectResponse,
    GcsObjectMetadata,
    UpdateObjectMetadataRequest,
    UpdateObjectMetadataResponse,
    DeleteObjectRequest,
    DeleteObjectResponse,
    ListObjectsRequest,
    ListObjectsResponse,
    ListBucketsRequest,
    ListBucketsResponse,
)


class GoogleGcsTokenVerifier(TokenVerifier):
    """Verifies a Google OAuth access token against Google's tokeninfo endpoint."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    GCS_AUTH_CONFIG.google_token_info_url,
                    params={"access_token": token},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return AccessToken(
                        token=token,
                        client_id=data.get("aud", "unknown"),
                        scopes=data.get("scope", "").split(),
                    )
        except Exception:
            pass
        return None


# Instantiate MCP Server
mcp = FastMCP(
    GCS_SERVER_CONFIG.server_name,
    stateless_http=GCS_SERVER_CONFIG.stateless_http,
    json_response=GCS_SERVER_CONFIG.json_response,
    host=GCS_SERVER_CONFIG.default_host,
    port=GCS_SERVER_CONFIG.default_port,
    debug=GCS_SERVER_CONFIG.debug,
    token_verifier=GoogleGcsTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(GCS_AUTH_CONFIG.google_accounts_issuer_url),
        resource_server_url=AnyHttpUrl(
            f"http://{GCS_SERVER_CONFIG.default_host}:{GCS_SERVER_CONFIG.default_port}"
        ),
    ),
)


@mcp.tool()
async def create_bucket(request: CreateBucketRequest) -> CreateBucketResponse:
    """
    Creates a new Google Cloud Storage bucket.

    Args:
        request: CreateBucketRequest -> The request parameters for bucket creation.

    Returns:
        CreateBucketResponse -> The result of the bucket creation operation.
    """
    logger.info(
        "Tool call: create_bucket("
        f"project_id={request.project_id}, bucket_name={request.bucket_name}, "
        f"location={request.location})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        name = await asyncio.to_thread(
            gcs_manager.create_bucket,
            request.bucket_name,
            request.location,
            request.project_id,
        )
        return CreateBucketResponse(
            project_id=request.project_id,
            bucket_name=name,
            location=request.location,
            execution_status="success",
            execution_message=(
                f"Successfully created bucket: {name} in project "
                f"{gcs_manager.resolve_project_id(request.project_id)}"
            ),
        )
    except Exception as e:
        return CreateBucketResponse(
            project_id=request.project_id,
            bucket_name=request.bucket_name,
            location=request.location,
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def update_bucket_labels(
    request: UpdateBucketLabelsRequest,
) -> UpdateBucketLabelsResponse:
    """
    Updates or sets labels on an existing GCS bucket.

    Args:
        request: UpdateBucketLabelsRequest -> The request parameters including bucket name and labels.

    Returns:
        UpdateBucketLabelsResponse -> The result of the label update operation.
    """
    logger.info(
        f"Tool call: update_bucket_labels(bucket_name={request.bucket_name}, labels={request.labels})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        updated_labels = await asyncio.to_thread(
            gcs_manager.update_bucket_labels, request.bucket_name, request.labels
        )
        return UpdateBucketLabelsResponse(
            bucket_name=request.bucket_name,
            labels=updated_labels,
            execution_status="success",
            execution_message=(
                f"Successfully updated labels for {request.bucket_name}: {updated_labels}"
            ),
        )
    except Exception as e:
        return UpdateBucketLabelsResponse(
            bucket_name=request.bucket_name,
            labels=request.labels,
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def upload_object(request: UploadObjectRequest) -> UploadObjectResponse:
    """
    Ingests an object from a source GCS URI into a destination bucket.
    This tool replaces direct uploads and implements automated authentication switching.

    Args:
        request: UploadObjectRequest -> The URI-based ingestion parameters.

    Returns:
        UploadObjectResponse -> The resulting destination URI and status.
    """
    logger.info(
        f"Tool call: upload_object(source={request.source_gcs_uri}, "
        f"dest_bucket={request.destination_bucket}, filename={request.filename})"
    )
    try:
        # 1. Determine Authentication Strategy
        # Logic: Use SA ONLY for internal landing-zone to KB pipeline.
        use_sa = (
            request.source_bucket == GCS_SERVER_CONFIG.landing_zone_bucket
            and request.destination_bucket == GCS_SERVER_CONFIG.kb_ingestion_bucket
        )

        # 2. Execute Copy Operation
        gcs_manager = _make_gcs_manager(use_sa=use_sa)
        blob = await asyncio.to_thread(
            gcs_manager.copy_blob,
            request.source_bucket,
            request.source_object,
            request.destination_bucket,
            request.destination_path,
        )

        dest_uri = f"gs://{request.destination_bucket}/{blob.name}"
        return UploadObjectResponse(
            destination_uri=dest_uri,
            execution_status="success",
            execution_message=f"Successfully ingested object to {dest_uri}",
        )
    except Exception as e:
        return UploadObjectResponse(
            destination_uri="",
            execution_status="error",
            execution_message=_format_execution_error(e),
        )
    finally:
        pass


@mcp.tool()
async def read_object(request: ReadObjectRequest) -> ReadObjectResponse:
    """
    Retrieves metadata and the canonical GCS URI for a specific file (blob).
    Ideal for preparing files for multi-modal LLM analysis via GCS URI reference.

    Args:
        request: ReadObjectRequest -> The request parameters (bucket, object).

    Returns:
        ReadObjectResponse -> The object URI and strictly typed metadata.
    """
    logger.info(
        f"Tool call: read_object(bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        blob = await asyncio.to_thread(
            gcs_manager.get_object_metadata,
            request.bucket_name,
            request.object_name,
        )

        # Extract and format metadata
        creation_dt = blob.time_created
        metadata = GcsObjectMetadata(
            mime_type=blob.content_type or "application/octet-stream",
            size_bytes=blob.size or 0,
            creation_date=creation_dt.strftime("%Y-%m-%d")
            if creation_dt
            else "unknown",
            creation_time=creation_dt.strftime("%H:%M:%S")
            if creation_dt
            else "unknown",
            updated_at=blob.updated.isoformat() if blob.updated else "unknown",
            custom_metadata=blob.metadata or {},
        )

        return ReadObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            gcs_uri=f"gs://{request.bucket_name}/{request.object_name}",
            metadata=metadata,
            execution_status="success",
            execution_message="Object metadata and URI retrieved successfully.",
        )
    except Exception as e:
        # Fallback empty metadata on error
        return ReadObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            gcs_uri=f"gs://{request.bucket_name}/{request.object_name}",
            metadata=GcsObjectMetadata(
                mime_type="application/octet-stream",
                size_bytes=0,
                creation_date="error",
                creation_time="error",
                updated_at="error",
                custom_metadata={},
            ),
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def update_object_metadata(
    request: UpdateObjectMetadataRequest,
) -> UpdateObjectMetadataResponse:
    """
    Updates the metadata of an existing object in GCS, such as content-type or custom metadata.

    Args:
        request: UpdateObjectMetadataRequest -> The request parameters for updating metadata.

    Returns:
        UpdateObjectMetadataResponse -> The updated metadata summary.
    """
    logger.info(
        "Tool call: update_object_metadata("
        f"bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        blob = await asyncio.to_thread(
            gcs_manager.update_object_metadata,
            request.bucket_name,
            request.object_name,
            request.metadata,
        )
        return UpdateObjectMetadataResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            metadata=blob.metadata or {},
            content_type=blob.content_type,
            execution_status="success",
            execution_message=(
                f"Successfully updated metadata for {request.object_name}."
            ),
        )
    except Exception as e:
        return UpdateObjectMetadataResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            metadata=request.metadata,
            content_type=request.metadata.get("content_type"),
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def delete_object(request: DeleteObjectRequest) -> DeleteObjectResponse:
    """
    Deletes an object from a GCS bucket.

    Args:
        request: DeleteObjectRequest -> The request parameters for deleting the object.

    Returns:
        DeleteObjectResponse -> The result of the deletion operation.
    """
    logger.info(
        f"Tool call: delete_object(bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        await asyncio.to_thread(
            gcs_manager.delete_object, request.bucket_name, request.object_name
        )
        return DeleteObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            execution_status="success",
            execution_message=(
                f"Successfully deleted object: {request.object_name} from bucket: {request.bucket_name}"
            ),
        )
    except Exception as e:
        return DeleteObjectResponse(
            bucket_name=request.bucket_name,
            object_name=request.object_name,
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def list_objects(request: ListObjectsRequest) -> ListObjectsResponse:
    """
    Lists objects in a GCS bucket, optionally filtered by prefix to simulate folders.

    Args:
        request: ListObjectsRequest -> The request parameters for listing objects.

    Returns:
        ListObjectsResponse -> A list of found object names.
    """
    logger.info(
        f"Tool call: list_objects(bucket_name={request.bucket_name}, prefix={request.prefix})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        blobs = await asyncio.to_thread(
            gcs_manager.list_blobs, request.bucket_name, request.prefix
        )
        return ListObjectsResponse(
            bucket_name=request.bucket_name,
            prefix=request.prefix,
            objects=blobs,
            execution_status="success",
            execution_message=(
                f"Found {len(blobs)} objects in {request.bucket_name} with prefix '{request.prefix or ''}'."
            ),
        )
    except Exception as e:
        return ListObjectsResponse(
            bucket_name=request.bucket_name,
            prefix=request.prefix,
            objects=[],
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def list_buckets(request: ListBucketsRequest) -> ListBucketsResponse:
    """
    Lists buckets available to the current project credentials,
    optionally filtered by bucket-name prefix.

    Args:
        request: ListBucketsRequest -> The request parameters for listing buckets.

    Returns:
        ListBucketsResponse -> A structured response with matching bucket names.
    """
    logger.info(
        f"Tool call: list_buckets(project_id={request.project_id}, prefix={request.prefix})"
    )
    try:
        gcs_manager = _make_gcs_manager()
        buckets = await asyncio.to_thread(
            gcs_manager.list_buckets, request.prefix, request.project_id
        )
        return ListBucketsResponse(
            project_id=request.project_id,
            prefix=request.prefix,
            buckets=buckets,
            execution_status="success",
            execution_message=(
                f"Found {len(buckets)} buckets with prefix '{request.prefix or ''}' "
                f"in project {gcs_manager.resolve_project_id(request.project_id)}."
            ),
        )
    except Exception as e:
        return ListBucketsResponse(
            project_id=request.project_id,
            prefix=request.prefix,
            buckets=[],
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


def _make_gcs_manager(use_sa: bool = False) -> GCSManager:
    """Creates a GCS manager using either the delegated user token or the environment SA."""
    if use_sa:
        creds = build_sa_credentials(scopes=GCS_API_CONFIG.read_write_scopes)
    else:
        access_token = _get_current_token()
        creds = build_gcs_credentials(
            access_token=access_token,
            scopes=GCS_API_CONFIG.read_write_scopes,
        )
    return GCSManager(creds, default_project=GCS_SERVER_CONFIG.default_project_id)


def _get_current_token() -> Optional[str]:
    """Returns the currently authenticated OAuth access token from MCP auth context."""
    token_obj = get_access_token()
    return token_obj.token if token_obj else None


def _format_execution_error(exc: Exception) -> str:
    """Returns a sanitized, user-facing execution message with permission normalization."""
    raw_message = _sanitize_sensitive_text(str(exc))
    lowered = raw_message.lower()
    if any(
        marker in lowered
        for marker in (
            "permission denied",
            "access denied",
            "insufficient permission",
            "insufficient permissions",
            "not authorized",
            "forbidden",
            "403",
        )
    ):
        return f"Permission Denied: {raw_message}"
    if any(marker in lowered for marker in ("not found", "404", "no such object")):
        return f"Object not found: {raw_message}"
    return raw_message


def _sanitize_sensitive_text(value: str) -> str:
    """Redacts common credential fragments from error messages before returning them."""
    sanitized = value or ""
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9._\-~+/]+=*", "Bearer [REDACTED]", sanitized
    )
    sanitized = re.sub(r"ya29\.[A-Za-z0-9._\-~+/]+=*", "ya29.[REDACTED]", sanitized)
    sanitized = re.sub(r"access_token=[^&\s]+", "access_token=[REDACTED]", sanitized)
    return sanitized
