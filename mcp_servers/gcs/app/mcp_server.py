import asyncio
import datetime
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
        f"Tool call: upload_object(source_bucket={request.source_bucket_name}, "
        f"source_object={request.source_object_name}, "
        f"dest_bucket={request.destination_bucket}, filename={request.filename})"
    )
    try:
        # 1. Determine Authentication Strategy
        # Logic: Use SA ONLY for internal landing-zone to KB pipeline.
        use_sa = (
            request.source_bucket_name.lower()
            == GCS_SERVER_CONFIG.landing_zone_bucket.lower()
            and request.destination_bucket.lower()
            == GCS_SERVER_CONFIG.kb_ingestion_bucket.lower()
        )
        if use_sa:
            logger.info(
                f"Using Service Account for restricted ingestion to {request.destination_bucket}"
            )

        # 2. Execute Copy Operation
        gcs_manager = _make_gcs_manager(use_sa=use_sa)
        await asyncio.to_thread(
            gcs_manager.copy_blob,
            request.source_bucket_name,
            request.source_object_name,
            request.destination_bucket,
            request.destination_path,
        )

        return UploadObjectResponse(
            destination_uri=f"gs://{request.destination_bucket}/{request.destination_path}",
            execution_status="success",
            execution_message=f"Successfully copied to gs://{request.destination_bucket}/{request.destination_path}",
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
    Retrieves file metadata and automatically streams external files into the Agent Landing Zone.

    This tool acts as a secure boundary between user data and the LLM context by executing three critical steps:
    1. Authorization Check: Uses human OAuth tokens to securely read from external buckets, while using the agent's Service Account (SA) for internal Landing Zone operations.
    2. Metadata Extraction: Fetches the source file's MIME type and size. This is required so the LLM understands the file context before processing.
    3. Zero-Copy Ingestion: If the file is external, it safely streams the data in chunks to the internal Landing Zone. This prevents the MCP container from crashing with Out of Memory (OOM)
       errors and allows the Vertex LLM to natively read massive files (e.g., PDFs, videos) directly from the GCS URI.

    Args:
        request: ReadObjectRequest -> Contains the target bucket and object name.

    Returns:
        ReadObjectResponse -> Contains the canonical Landing Zone GCS URI and strictly typed metadata.
    """
    logger.info(
        f"Tool call: read_object(bucket_name={request.bucket_name}, object_name={request.object_name})"
    )
    try:
        # 1. Determine if we are reading from the Landing Zone directly
        is_landing_zone = request.bucket_name == GCS_SERVER_CONFIG.landing_zone_bucket

        if is_landing_zone:
            # 2a. Internal Landing Zone Authorization
            # Users do not have direct IAM access to the Landing Zone, so we must use the Service Account.
            # To prevent IDOR (reading other users' files), we strictly validate that the requested
            # object falls within the current user's namespace.
            app_name = request.dependencies.app_name
            user_id = request.dependencies.user_id
            expected_prefix = f"{app_name}/{user_id}/"

            if not request.object_name.startswith(expected_prefix):
                raise PermissionError(
                    "Access denied: You can only read files within your own landing zone namespace."
                )

            use_sa = True
            logger.info(
                f"Using Service Account for landing zone read, validated namespace: {expected_prefix}"
            )
        else:
            # 2b. External Bucket Authorization
            # For any other bucket, we MUST use the user's OAuth token to ensure they have IAM read access.
            use_sa = False

        # 3. Fetch the metadata to ensure the file exists and we know its size/type
        gcs_manager_source = _make_gcs_manager(use_sa=use_sa)
        source_blob = await asyncio.to_thread(
            gcs_manager_source.get_object_metadata,
            request.bucket_name,
            request.object_name,
        )

        creation_dt = source_blob.time_created
        source_metadata = GcsObjectMetadata(
            mime_type=source_blob.content_type or "application/octet-stream",
            size_bytes=source_blob.size or 0,
            creation_date=creation_dt.strftime("%Y-%m-%d")
            if creation_dt
            else "unknown",
            creation_time=creation_dt.strftime("%H:%M:%S")
            if creation_dt
            else "unknown",
            updated_at=source_blob.updated.isoformat()
            if source_blob.updated
            else "unknown",
            custom_metadata=source_blob.metadata or {},
        )

        # final_uri is the GCS URI where the agent will read the file from.
        # It always contains the landing zone bucket, which is the one the agent has access to.
        final_uri = f"gs://{request.bucket_name}/{request.object_name}"

        if not is_landing_zone:
            # Construct a safe path inside the landing zone using the injected identity
            app_name = request.dependencies.app_name
            user_id = request.dependencies.user_id
            session_id = request.dependencies.session_id

            current_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y%m%dT%H%M%SZ"
            )
            original_filename = request.object_name.split("/")[-1]

            # Sanitize the filename to avoid URI parsing issues in Vertex AI with spaces and special characters
            sanitized_filename = re.sub(r"[^a-zA-Z0-9.\-_]", "_", original_filename)

            # destination path constructed based on the path defined in .agents/mcp-server-guide.md
            dest_object = f"{app_name}/{user_id}/{session_id}/gcs-{current_timestamp}-{sanitized_filename}"

            logger.info(f"Ingesting external file to landing zone: {dest_object}")

            # We must use SA to write to the landing zone, because the user's OAuth token doesn't have access to it
            gcs_manager_destination = _make_gcs_manager(use_sa=True)

            # 5. Stream the file chunk by chunk to avoid Out Of Memory
            # We pass source_blob.content_type directly to the stream to save a dedicated API call later
            await asyncio.to_thread(
                gcs_manager_source.stream_to_landing_zone,
                request.bucket_name,
                request.object_name,
                GCS_SERVER_CONFIG.landing_zone_bucket,
                dest_object,
                gcs_manager_destination,
                source_blob.content_type,
            )

            # 6. Only execute an extra patch API call if the original blob had custom_metadata
            if source_blob.metadata:
                await asyncio.to_thread(
                    gcs_manager_destination.update_object_metadata,
                    GCS_SERVER_CONFIG.landing_zone_bucket,
                    dest_object,
                    {"custom_metadata": source_blob.metadata},
                )
            final_uri = f"gs://{GCS_SERVER_CONFIG.landing_zone_bucket}/{dest_object}"
            exec_msg = f"File gs://{request.bucket_name}/{request.object_name} was securely copied to the internal Landing Zone ({final_uri}) for native reading."
        else:
            exec_msg = "Object metadata and URI retrieved successfully."

        return ReadObjectResponse(
            gcs_uri=final_uri,
            mime_type=source_metadata.mime_type,
            metadata=source_metadata,
            inject_file_data=True,
            execution_status="success",
            execution_message=exec_msg,
        )
    except Exception as e:
        # Fallback empty metadata on error
        return ReadObjectResponse(
            gcs_uri=f"gs://{request.bucket_name}/{request.object_name}",
            mime_type="application/octet-stream",
            metadata=GcsObjectMetadata(
                mime_type="application/octet-stream",
                size_bytes=0,
                creation_date="error",
                creation_time="error",
                updated_at="error",
                custom_metadata={},
            ),
            inject_file_data=False,
            execution_status="error",
            execution_message=_format_execution_error(e),
        )


@mcp.tool()
async def update_object_metadata(
    request: UpdateObjectMetadataRequest,
) -> UpdateObjectMetadataResponse:
    """
    Updates the metadata of an existing object in GCS, such as content-type or custom metadata.
    This tool implements automated SA switching for restricted ingestion buckets.

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
        # Determine Authentication Strategy
        use_sa = (
            request.bucket_name.lower() == GCS_SERVER_CONFIG.kb_ingestion_bucket.lower()
        )
        if use_sa:
            logger.info(
                f"Using Service Account for metadata update on restricted bucket {request.bucket_name}"
            )

        gcs_manager = _make_gcs_manager(use_sa=use_sa)
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
        creds = build_sa_credentials()
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
