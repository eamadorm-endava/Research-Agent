from loguru import logger
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

import os
from google.cloud import storage

# Import unified schemas mapping layouts
from .schemas import (
    ExecutionStatus,
    FolderInfo,
    PersonalData,
    AttachmentInfo,
    EmailInformationPreview,
    EmailInformationFull,
    GetProfileRequest,
    GetProfileResponse,
    ListFoldersRequest,
    ListFoldersResponse,
    ListEmailsRequest,
    ListEmailsResponse,
    ReadEmailRequest,
    ReadEmailResponse,
    ReadFileRequest,
    ReadFileResponse,
    CreateDraftRequest,
    CreateDraftResponse,
    SendMailRequest,
    SendMailResponse,
    SendDraftRequest,
    SendDraftResponse,
)
from .config import OUTLOOK_SERVER_CONFIG
from .security import MicrosoftTokenVerifier, create_outlook_client


# =====================================================================
# Server Instantiation & Authentication Guard-rails
# =====================================================================

mcp = FastMCP(
    OUTLOOK_SERVER_CONFIG.server_name,
    stateless_http=OUTLOOK_SERVER_CONFIG.stateless_http,
    host=OUTLOOK_SERVER_CONFIG.default_host,
    port=OUTLOOK_SERVER_CONFIG.default_port,
    token_verifier=MicrosoftTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("https://login.microsoftonline.com/common/v2.0"),
        resource_server_url=AnyHttpUrl(
            f"http://{OUTLOOK_SERVER_CONFIG.default_host}:{OUTLOOK_SERVER_CONFIG.default_port}"
        ),
    ),
)


# =====================================================================
# Structural Conversion & Content Sanitization Helpers
# =====================================================================


def to_email_preview(msg_dict: dict) -> EmailInformationPreview:
    """Maps cleaned client dictionary objects into strict Pydantic models."""
    return EmailInformationPreview(
        email_id=msg_dict.get("email_id"),
        sender_data=PersonalData(**msg_dict.get("sender_data", {})),
        sent_to=[PersonalData(**r) for r in msg_dict.get("sent_to", [])],
        subject=msg_dict.get("subject", ""),
        email_body_preview=msg_dict.get("email_body_preview", ""),
        received_date=msg_dict.get("received_date"),
        has_attachments=msg_dict.get("has_attachments", False),
        is_read=msg_dict.get("is_read", True),
        folder_name=msg_dict.get("folder_name", "Unknown Folder"),
    )


# async def upload_to_gcs_landing_zone(filename: str, data_bytes: bytes, context: str = "default") -> str:
#     """
#     Placeholder/Hook for your internal cloud bucket storage ingestion engine.
#     Replace or import this with your exact cloud utilities module.
#     """
#     logger.info(f"Uploading {filename} ({len(data_bytes)} bytes) to GCS storage bucket...")
#     # Simulate extraction layer execution path uri return
#     return f"gs://outlook-mcp-landing-zone/{context}/{filename}"

# logger = logging.getLogger(__name__)


async def upload_to_gcs_landing_zone(
    filename: str, data_bytes: bytes, context: str = "default"
) -> str:
    """
    Streams binary file payloads directly into the centralized GCS Landing Zone bucket,
    utilizing credentials from the environment.
    """
    # 🌟 1. Dynamically pull the bucket name from your environment config (.env)
    bucket_name = os.environ.get("OUTLOOK_LANDING_ZONE_BUCKET")

    if not bucket_name:
        # Fallback safety in case the environment variable didn't load properly
        raise ValueError(
            "CRITICAL: OUTLOOK_LANDING_ZONE_BUCKET environment variable is not set."
        )

    logger.info(
        f"🚀 Initializing GCS upload for {filename} ({len(data_bytes)} bytes) to bucket: {bucket_name}"
    )

    try:
        # 2. Initialize the official Google Cloud Storage Client
        # It automatically locates credentials via GOOGLE_APPLICATION_CREDENTIALS or gcloud auth
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        # 3. Define the destination path (Blob object name) inside the bucket
        blob_path = f"{context}/{filename}"
        blob = bucket.blob(blob_path)

        # 4. Stream the raw byte array directly up to the cloud landing zone
        blob.upload_from_string(data_bytes, content_type="application/octet-stream")

        gcs_uri = f"gs://{bucket_name}/{blob_path}"
        logger.info(f"✅ Successfully ingested file into landing zone: {gcs_uri}")

        return gcs_uri

    except Exception as e:
        logger.error(
            f"❌ Failed to stream file payload to Google Cloud Storage: {str(e)}"
        )
        raise e


# =====================================================================
# Account & Context Profile Lookups
# =====================================================================


@mcp.tool()
async def outlook_get_profile(request: GetProfileRequest) -> GetProfileResponse:
    """Retrieves authenticated context metadata for the currently active user profile."""
    try:
        client = create_outlook_client()
        profile = await client.get_profile()

        return GetProfileResponse(
            display_name=profile.get("displayName"),
            email=profile.get("mail") or profile.get("userPrincipalName"),
            user_id=profile.get("id"),
        )
    except Exception as exc:
        logger.exception("Error during outlook_get_profile execution")
        return GetProfileResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


# =====================================================================
# Tool 1: Mailbox Architecture Folder Crawls
# =====================================================================


@mcp.tool()
async def outlook_list_folders(request: ListFoldersRequest) -> ListFoldersResponse:
    """Lists all available root mail folders (Inbox, Sent Items, Junk Email, and custom subfolders).
    CRITICAL: Always run this tool first if the user mentions a specific folder name or location,
    in order to resolve the correct folder target before searching or reading.
    """
    try:
        client = create_outlook_client()
        raw_folders = await client.list_folders()

        mapped_folders = [
            FolderInfo(
                folder_id=f["id"],
                display_name=f["displayName"],
                total_item_count=f.get("totalItemCount", 0),
                unread_item_count=f.get("unreadItemCount", 0),
            )
            for f in raw_folders
        ]
        return ListFoldersResponse(folders=mapped_folders)
    except Exception as exc:
        logger.exception("Error during outlook_list_folders execution")
        return ListFoldersResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


# =====================================================================
# Tool 2: Consolidated List, Advanced Filter, & Paginated KQL Search
# =====================================================================


@mcp.tool()
async def outlook_list_emails(request: ListEmailsRequest) -> ListEmailsResponse:
    """
    Searches and lists recent emails across mailbox scopes utilizing advanced token-efficient previews.
    Supports complex searching via dates, sender details, subject patterns, and read statuses.
    If a user specifies a non-standard folder location, you must call outlook_list_folders
    first to verify its existence and fetch its unique operational context identifier.
    """
    try:
        client = create_outlook_client()
        messages, total_count = await client.list_emails(request)

        objects_found = [to_email_preview(msg) for msg in messages]

        # Calculate pagination limits safely
        total_pages = max(1, (total_count + request.limit - 1) // request.limit)
        has_next = request.page < total_pages

        return ListEmailsResponse(
            execution_status=ExecutionStatus.SUCCESS,
            objects_found=objects_found,
            total_items_matched=total_count,
            current_page=request.page,
            total_pages=total_pages,
            has_next=has_next,
        )
    except Exception as exc:
        logger.exception("Error during outlook_list_emails execution")
        return ListEmailsResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
            objects_found=[],
            total_items_matched=0,
        )


# =====================================================================
# Tool 3: Exhaustive Message Inspection & Extraction
# =====================================================================


@mcp.tool()
async def outlook_read_email(request: ReadEmailRequest) -> ReadEmailResponse:
    """Retrieves full body content string matrices and structural metadata for analytical context reading."""
    try:
        client = create_outlook_client()
        raw_msg = await client.read_email(request.email_id)

        # Guard rail: If raw_msg is a Pydantic model or object, safely convert it to a dictionary
        if hasattr(raw_msg, "model_dump"):
            msg_dict = raw_msg.model_dump()
        elif hasattr(raw_msg, "__dict__"):
            msg_dict = getattr(raw_msg, "__dict__")
        else:
            msg_dict = raw_msg

        # 1. Safely extract sender data
        from_obj = msg_dict.get("from") or msg_dict.get("sender_data") or {}
        if isinstance(from_obj, dict):
            email_addr = from_obj.get("emailAddress") or {}
            sender_name = email_addr.get("name") or from_obj.get("name")
            sender_email = (
                email_addr.get("address")
                or from_obj.get("email")
                or "unknown@domain.com"
            )
        else:
            # If from_obj is an object
            sender_name = getattr(from_obj, "name", None)
            sender_email = getattr(from_obj, "email", "unknown@domain.com")

        sender_payload = PersonalData(name=sender_name, email=sender_email)

        # 2. Safely extract recipients list
        to_recipients = []
        raw_recipients = msg_dict.get("toRecipients") or msg_dict.get("sent_to") or []
        for r in raw_recipients:
            if isinstance(r, dict):
                addr = r.get("emailAddress") or r
                to_recipients.append(
                    PersonalData(
                        name=addr.get("name"),
                        email=addr.get("address")
                        or addr.get("email")
                        or "unknown@domain.com",
                    )
                )
            else:
                to_recipients.append(
                    PersonalData(
                        name=getattr(r, "name", None),
                        email=getattr(r, "email", "unknown@domain.com"),
                    )
                )

        # 3. Safely map attachments array
        attachments_list = []
        raw_attachments = msg_dict.get("attachments") or []
        for a in raw_attachments:
            if isinstance(a, dict):
                if "id" in a or "attachment_id" in a:
                    attachments_list.append(
                        AttachmentInfo(
                            file_name=a.get("name")
                            or a.get("file_name")
                            or "Unnamed_Attachment",
                            mime_type=a.get("contentType")
                            or a.get("mime_type")
                            or "application/octet-stream",
                            attachment_id=a.get("id") or a.get("attachment_id"),
                            size=a.get("size", 0),
                        )
                    )
            else:
                attachments_list.append(
                    AttachmentInfo(
                        file_name=getattr(
                            a, "file_name", getattr(a, "name", "Unnamed_Attachment")
                        ),
                        mime_type=getattr(
                            a,
                            "mime_type",
                            getattr(a, "contentType", "application/octet-stream"),
                        ),
                        attachment_id=getattr(a, "attachment_id", getattr(a, "id", "")),
                        size=getattr(a, "size", 0),
                    )
                )

        # 4. Final assembly with standard key fallbacks
        body_obj = msg_dict.get("body") or {}
        body_content = (
            body_obj.get("content", "")
            if isinstance(body_obj, dict)
            else getattr(body_obj, "content", "")
        )
        if not body_content and isinstance(msg_dict.get("email_body"), str):
            body_content = msg_dict.get("email_body")

        full_info = EmailInformationFull(
            email_id=msg_dict.get("id") or msg_dict.get("email_id"),
            sender_data=sender_payload,
            sent_to=to_recipients,
            subject=msg_dict.get("subject", ""),
            email_body_preview=msg_dict.get("bodyPreview")
            or msg_dict.get("email_body_preview")
            or "",
            received_date=msg_dict.get("receivedDateTime")
            or msg_dict.get("received_date"),
            has_attachments=msg_dict.get("hasAttachments")
            or msg_dict.get("has_attachments")
            or False,
            is_read=msg_dict.get("isRead") or msg_dict.get("is_read") or True,
            folder_name=msg_dict.get("folder_name", "Unknown Folder"),
            email_body=body_content,
            attachments=attachments_list,
        )

        return ReadEmailResponse(email=full_info)

    except Exception as exc:
        logger.exception("Error during outlook_read_email execution")
        return ReadEmailResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


# =====================================================================
# Tool 4: Direct Attachment Streaming & Cloud Storage Landings
# =====================================================================

# @mcp.tool()
# async def outlook_read_email_attachment(request: ReadFileRequest) -> ReadFileResponse:
#     """Streams target binary data directly from Graph into staging buckets."""
#     try:
#         client = create_outlook_client()

#         # Extract raw file stream array straight from downstream Graph targets
#         file_bytes = await client.download_attachment(request.email_id, request.file_id)

#         # Pipeline binary payloads to Cloud Landing Zones
#         gcs_destination_uri = await upload_to_gcs_landing_zone(
#             filename=request.filename,
#             data_bytes=file_bytes,
#             context=request.email_id
#         )

#         return ReadFileResponse(
#             execution_status=ExecutionStatus.SUCCESS,
#             gcs_uri=gcs_destination_uri,
#             filename=request.filename,
#             mime_type=None,  # Available during inline inspection runs
#             inject_file_data=True
#         )
#     except Exception as exc:
#         logger.exception("Error during outlook_read_email_attachment execution")
#         return ReadFileResponse(
#             execution_status=ExecutionStatus.ERROR,
#             error_message=str(exc),
#             gcs_uri=None,
#             filename=request.filename,
#             inject_file_data=False
#         )


@mcp.tool()
async def outlook_read_email_attachment(request: ReadFileRequest) -> ReadFileResponse:
    """
    Streams target binary data directly from Graph into GCS Landing Zone staging buckets,
    setting inject_file_data to True on successful handoffs.
    """
    try:
        client = create_outlook_client()

        # 1. Extract raw file bytes (auto-handling base64 variations internally)
        file_bytes = await client.download_attachment(request.email_id, request.file_id)

        if not file_bytes:
            raise ValueError("Retrieved attachment payload contains 0 bytes.")

        # 2. Pipeline binary payload directly to Google Cloud Landing Zone
        # Ensure this helper utilizes os.environ.get("LANDING_ZONE_BUCKET") internally
        gcs_destination_uri = await upload_to_gcs_landing_zone(
            filename=request.filename, data_bytes=file_bytes, context=request.email_id
        )

        # 3. Return response with inject_file_data set explicitly to True
        return ReadFileResponse(
            execution_status=ExecutionStatus.SUCCESS,
            gcs_uri=gcs_destination_uri,
            filename=request.filename,
            mime_type=None,  # Available during downstream vectorization runs
            inject_file_data=True,
        )

    except Exception as exc:
        logger.exception(
            f"Error during outlook_read_email_attachment execution for file {request.filename}"
        )
        return ReadFileResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
            gcs_uri=None,
            filename=request.filename,
            inject_file_data=False,
        )


# =====================================================================
# Outbound Transactional Operations (Preserved Systems)
# =====================================================================


@mcp.tool()
async def outlook_create_draft(request: CreateDraftRequest) -> CreateDraftResponse:
    """Generates an unsent email message shell matching specified target recipients."""
    try:
        client = create_outlook_client()
        draft = await client.create_draft(
            to=request.to,
            cc=request.cc,
            subject=request.subject,
            body=request.body,
        )

        return CreateDraftResponse(
            draft_id=draft.get("id"),
            web_link=draft.get("webLink"),
        )
    except Exception as exc:
        logger.exception("Error during outlook_create_draft execution")
        return CreateDraftResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_send_mail(request: SendMailRequest) -> SendMailResponse:
    """Dispatches a text/HTML transactional message immediately to target users."""
    try:
        client = create_outlook_client()
        await client.send_mail(
            to=request.to,
            cc=request.cc,
            subject=request.subject,
            body=request.body,
            save_to_sent_items=request.save_to_sent_items,
        )

        return SendMailResponse(sent=True)
    except Exception as exc:
        logger.exception("Error during outlook_send_mail execution")
        return SendMailResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_send_draft(request: SendDraftRequest) -> SendDraftResponse:
    """Triggers the execution delivery run for a pre-staged draft message template."""
    try:
        client = create_outlook_client()
        await client.send_draft(request.draft_id)

        return SendDraftResponse(sent=True)
    except Exception as exc:
        logger.exception("Error during outlook_send_draft execution")
        return SendDraftResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )
