from loguru import logger
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

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
    CalendarEventPreview,
    CalendarEventFull,
    ListCalendarEventsRequest,
    ListCalendarEventsResponse,
    ReadCalendarEventRequest,
    ReadCalendarEventResponse,
    ReadCalendarEventAttachmentRequest,
    ReadCalendarEventAttachmentResponse,
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
    """
    Maps cleaned client dictionary objects into strict Pydantic models.

    Args:
        msg_dict: dict -> The raw message dictionary from the Graph API.

    Returns:
        EmailInformationPreview -> The Pydantic model representing the email preview.
    """
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


# =====================================================================
# Account & Context Profile Lookups
# =====================================================================


@mcp.tool()
async def outlook_get_profile(request: GetProfileRequest) -> GetProfileResponse:
    """
    Retrieves authenticated context metadata for the currently active user profile.

    Args:
        request: GetProfileRequest -> The request payload for profile retrieval.

    Returns:
        GetProfileResponse -> The response payload containing profile metadata.
    """
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
    """
    Lists all available root mail folders (Inbox, Sent Items, Junk Email, and custom subfolders).
    CRITICAL: Always run this tool first if the user mentions a specific folder name or location,
    in order to resolve the correct folder target before searching or reading.

    Args:
        request: ListFoldersRequest -> The request payload for listing folders.

    Returns:
        ListFoldersResponse -> The response payload containing the list of folders.
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
    CRITICAL AGENT INSTRUCTION: Always return ONLY the items found on the current requested page.
    Even if the user asks for 'all' emails, do NOT auto-loop through pages or fetch subsequent pages
    in a single turn. Present the first page to the user and inform them that more pages are available
    using the 'has_next' and 'total_pages' metadata.

    Args:
        request: ListEmailsRequest -> The request payload with search and filter parameters.

    Returns:
        ListEmailsResponse -> The response payload with paginated matching emails.
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
    """
    Retrieves full body content string matrices and structural metadata for analytical context reading.

    Args:
        request: ReadEmailRequest -> The request payload containing the email ID.

    Returns:
        ReadEmailResponse -> The response payload containing full email details.
    """
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

    Args:
        request: ReadFileRequest -> The request payload with email ID and attachment ID.

    Returns:
        ReadFileResponse -> The response containing the GCS URI of the injected file.
    """
    try:
        if not request.dependencies:
            raise ValueError("Agent dependencies must be provided to ingest files.")

        client = create_outlook_client()
        result = await client.read_attachment(
            email_id=request.email_id,
            attachment_id=request.file_id,
            dependencies=request.dependencies,
            is_calendar=False,
        )

        if result.get("is_reference"):
            return ReadFileResponse(
                execution_status=ExecutionStatus.ERROR,
                error_message=f"This is a cloud reference attachment named '{result.get('name')}'. Please use the OneDrive or SharePoint MCPs to read this file via its link: {result.get('provider_link')}",
                gcs_uri=None,
                filename=request.filename,
                inject_file_data=False,
            )

        return ReadFileResponse(
            execution_status=ExecutionStatus.SUCCESS,
            gcs_uri=result["gcs_uri"],
            filename=result["filename"],
            mime_type=result["mime_type"],
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
# Calendar Operations
# =====================================================================


@mcp.tool()
async def outlook_list_calendar_events(
    request: ListCalendarEventsRequest,
) -> ListCalendarEventsResponse:
    """
    Lists calendar events using Microsoft Graph API with optional date/time and text filters.

    Args:
        request: ListCalendarEventsRequest -> The request payload containing search parameters

    Returns:
        ListCalendarEventsResponse -> The response containing matching events
    """
    try:
        client = create_outlook_client()
        events, _ = await client.list_calendar_events(
            max_events=request.max_events,
            date_min=request.date_min,
            time_min=request.time_min,
            date_max=request.date_max,
            time_max=request.time_max,
            sort_order=request.sort_order,
            search_term=request.search_term,
        )

        parsed_events = [CalendarEventPreview(**event_data) for event_data in events]

        from datetime import datetime, timezone

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return ListCalendarEventsResponse(
            server_current_time_utc=current_time, events=parsed_events
        )
    except Exception as exception:
        logger.exception("Error during outlook_list_calendar_events execution")
        return ListCalendarEventsResponse(
            execution_status=ExecutionStatus.ERROR, error_message=str(exception)
        )


@mcp.tool()
async def outlook_read_calendar_event(
    request: ReadCalendarEventRequest,
) -> ReadCalendarEventResponse:
    """
    Fetches the full details of a specific calendar event including its attachments.

    Args:
        request: ReadCalendarEventRequest -> The request payload containing the event ID

    Returns:
        ReadCalendarEventResponse -> The response containing complete event details
    """
    try:
        client = create_outlook_client()
        event_dict = await client.read_calendar_event(request.event_id)

        return ReadCalendarEventResponse(event=CalendarEventFull(**event_dict))
    except Exception as exception:
        logger.exception("Error during outlook_read_calendar_event execution")
        return ReadCalendarEventResponse(
            execution_status=ExecutionStatus.ERROR, error_message=str(exception)
        )


@mcp.tool()
async def outlook_read_calendar_event_attachment(
    request: ReadCalendarEventAttachmentRequest,
) -> ReadCalendarEventAttachmentResponse:
    """
    Downloads a file attachment from a calendar event to the GCS Landing Zone.

    Args:
        request: ReadCalendarEventAttachmentRequest -> The request payload containing event and attachment IDs

    Returns:
        ReadCalendarEventAttachmentResponse -> The response containing the GCS URI of the injected file
    """
    try:
        if not request.dependencies:
            raise ValueError("Agent dependencies must be provided to ingest files.")

        client = create_outlook_client()
        result = await client.read_attachment(
            email_id=request.event_id,
            attachment_id=request.file_id,
            dependencies=request.dependencies,
            is_calendar=True,
        )

        if result.get("is_reference"):
            return ReadCalendarEventAttachmentResponse(
                execution_status=ExecutionStatus.ERROR,
                error_message=f"This is a cloud reference attachment named '{result.get('name')}'. Please use the OneDrive or SharePoint MCPs to read this file via its link: {result.get('provider_link')}",
                gcs_uri=None,
                file_name=request.filename,
                inject_file_data=False,
            )

        return ReadCalendarEventAttachmentResponse(
            execution_status=ExecutionStatus.SUCCESS,
            gcs_uri=result["gcs_uri"],
            file_name=result["filename"],
            mime_type=result["mime_type"],
            inject_file_data=True,
        )

    except Exception as exc:
        logger.exception(
            "Error during outlook_read_calendar_event_attachment execution"
        )
        return ReadCalendarEventAttachmentResponse(
            execution_status=ExecutionStatus.ERROR, error_message=str(exc)
        )
