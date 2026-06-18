import asyncio
from loguru import logger
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl
from .schemas import (
    CreateDraftRequest,
    CreateDraftResponse,
    ExecutionStatus,
    GetMessageRequest,
    GetMessageResponse,
    GetProfileRequest,
    GetProfileResponse,
    ListMessagesRequest,
    ListMessagesResponse,
    MessageSummary,
    SearchMessagesRequest,
    SearchMessagesResponse,
    SendDraftRequest,
    SendDraftResponse,
    SendMailRequest,
    SendMailResponse,
)
from .config import OUTLOOK_SERVER_CONFIG
from .security import MicrosoftTokenVerifier, create_outlook_client


# Instantiate MCP Server
mcp = FastMCP(
    OUTLOOK_SERVER_CONFIG.server_name,
    stateless_http=OUTLOOK_SERVER_CONFIG.stateless_http,
    host=OUTLOOK_SERVER_CONFIG.default_host,
    port=OUTLOOK_SERVER_CONFIG.default_port,
    token_verifier=MicrosoftTokenVerifier(),
    # Entra ID token validation uses a standard OAuth issuer
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("https://login.microsoftonline.com/common/v2.0"),
        resource_server_url=AnyHttpUrl(
            f"http://{OUTLOOK_SERVER_CONFIG.default_host}:{OUTLOOK_SERVER_CONFIG.default_port}"
        ),
    ),
)


def to_message_summary(raw: dict) -> MessageSummary:
    sender = (
        raw.get("from", {})
        .get("emailAddress", {})
        .get("address")
    )

    return MessageSummary(
        id=raw.get("id"),
        subject=raw.get("subject"),
        sender=sender,
        received_at=raw.get("receivedDateTime"),
        body_preview=raw.get("bodyPreview"),
        has_attachments=raw.get("hasAttachments", False),
        web_link=raw.get("webLink"),
    )


@mcp.tool()
async def outlook_get_profile(request: GetProfileRequest) -> GetProfileResponse:
    try:
        client = create_outlook_client()

        profile = await client.get_profile()

        return GetProfileResponse(
            display_name=profile.get("displayName"),
            email=profile.get("mail") or profile.get("userPrincipalName"),
            user_id=profile.get("id"),
        )
    except Exception as exc:
        return GetProfileResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_list_messages(request: ListMessagesRequest) -> ListMessagesResponse:
    try:
        client = create_outlook_client()

        raw_messages = await client.list_messages(
            folder=request.folder,
            top=request.top,
            unread_only=request.unread_only,
        )

        return ListMessagesResponse(
            messages=[to_message_summary(message) for message in raw_messages],
        )
    except Exception as exc:
        return ListMessagesResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_search_messages(request: SearchMessagesRequest) -> SearchMessagesResponse:
    try:
        client = create_outlook_client()
        raw_messages = await client.search_messages(query=request.query, top=request.top)

        return SearchMessagesResponse(
            messages=[to_message_summary(message) for message in raw_messages],
        )
    except Exception as exc:
        return SearchMessagesResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_get_message(request: GetMessageRequest) -> GetMessageResponse:
    try:
        client = create_outlook_client()
        raw = await client.get_message(request.message_id)

        sender = raw.get("from", {}).get("emailAddress", {}).get("address")
        body = raw.get("body", {}) or {}

        return GetMessageResponse(
            id=raw.get("id"),
            subject=raw.get("subject"),
            sender=sender,
            to_recipients=[
                r.get("emailAddress", {}).get("address")
                for r in raw.get("toRecipients", [])
                if r.get("emailAddress", {}).get("address")
            ],
            cc_recipients=[
                r.get("emailAddress", {}).get("address")
                for r in raw.get("ccRecipients", [])
                if r.get("emailAddress", {}).get("address")
            ],
            received_at=raw.get("receivedDateTime"),
            body_content_type=body.get("contentType"),
            body=body.get("content"),
            attachments=[
                {
                    "id": attachment.get("id"),
                    "name": attachment.get("name"),
                    "content_type": attachment.get("contentType"),
                    "size": attachment.get("size"),
                }
                for attachment in raw.get("attachments", [])
            ],
        )
    except Exception as exc:
        return GetMessageResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_create_draft(request: CreateDraftRequest) -> CreateDraftResponse:
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
        return CreateDraftResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_send_mail(request: SendMailRequest) -> SendMailResponse:
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
        return SendMailResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )


@mcp.tool()
async def outlook_send_draft(request: SendDraftRequest) -> SendDraftResponse:
    try:
        client = create_outlook_client()
        await client.send_draft(request.draft_id)

        return SendDraftResponse(sent=True)
    except Exception as exc:
        return SendDraftResponse(
            execution_status=ExecutionStatus.ERROR,
            error_message=str(exc),
        )