"""Authenticated Agent Engine sessions and SSE responses."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from agent.core_agent.security.token_store import token_store

from ..agent_client import get_remote_agent
from ..auth import get_current_user
from ..config import UI_CONFIG

router = APIRouter()


class ChatRequest(BaseModel):
    """Bound input size and allow the client to resume its own session."""

    message: str = Field(min_length=1, max_length=32000)
    session_id: str | None = Field(default=None, max_length=256)


def check_missing_providers(user_id: str) -> list[str]:
    """Check only explicitly required providers, rather than blocking every source."""
    return [
        provider
        for provider in UI_CONFIG.REQUIRED_PROVIDERS
        if not token_store.get_valid_access_token(user_id, provider)
    ]


def encode_event(event: dict) -> str:
    """Encode one complete SSE message."""
    return f"data: {json.dumps(event)}\n\n"


@router.post("/")
async def chat_stream(body: ChatRequest, user_id: str = Depends(get_current_user)):
    """Invoke the remote app using the verified user for session ownership."""
    missing = await run_in_threadpool(check_missing_providers, user_id)
    if missing:
        return StreamingResponse(
            iter(
                [
                    encode_event(
                        {
                            "type": "AUTH_REQUIRED",
                            "missing_providers": missing,
                        }
                    )
                ]
            ),
            media_type="text/event-stream",
        )
    remote_app = await run_in_threadpool(get_remote_agent)
    session_id = body.session_id
    if session_id:
        try:
            session = await remote_app.async_get_session(
                user_id=user_id, session_id=session_id
            )
        except Exception:  # noqa: BLE001 - Hide remote session lookup details
            raise HTTPException(404, "Session is unavailable") from None
        if not session or session.get("userId", session.get("user_id")) != user_id:
            raise HTTPException(
                403, "Session does not belong to the authenticated user"
            )
    else:
        session = await remote_app.async_create_session(user_id=user_id)
        session_id = session["id"]
    return StreamingResponse(
        generate_stream(remote_app, user_id, session_id, body.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )


async def generate_stream(remote_app, user_id: str, session_id: str, message: str):
    """Stream output without logging user content or presenting errors as success."""
    yield encode_event({"type": "session_info", "session_id": session_id})
    try:
        async for event in remote_app.async_stream_query(
            user_id=user_id,
            session_id=session_id,
            message=message,
        ):
            yield encode_event({"type": "agent_event", "payload": event})
        yield encode_event({"type": "done"})
    except Exception:  # noqa: BLE001 - API/UI boundary must not disclose credentials
        get_remote_agent.cache_clear()
        logger.warning("Agent stream failed")
        yield encode_event(
            {"type": "error", "message": "Agent request failed. Please retry."}
        )
