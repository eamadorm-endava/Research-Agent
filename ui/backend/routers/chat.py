import json
from typing import Annotated

import vertexai
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

# In a real scenario, this would use vertexai SDK
# e.g., from vertexai.preview import reasoning_engines
# For now, we mock the stream to demonstrate the architecture
from vertexai import agent_engines

from agent.core_agent.config import GCP_CONFIG

from ..config import UI_CONFIG
from ..limits import limiter, request_limit
from .oauth import check_missing_providers, get_current_user

router = APIRouter()

# Initialize Vertex AI
vertexai.init(project=GCP_CONFIG.PROJECT_ID, location=GCP_CONFIG.REGION)

# Initialize the remote app globally to reuse the connection
try:
    remote_app = agent_engines.get(UI_CONFIG.AGENT_RESOURCE_NAME)
    logger.info(
        f"Successfully connected to remote agent engine: {UI_CONFIG.AGENT_RESOURCE_NAME}"
    )
except Exception:  # noqa: BLE001 - SDK boundary reports unavailable without credential details
    logger.error("Failed to connect to the configured Agent Engine")
    remote_app = None


class ChatRequest(BaseModel):
    message: Annotated[
        str,
        Field(
            min_length=1, max_length=32000, description="User message for the agent."
        ),
    ]
    session_id: Annotated[
        str | None,
        Field(default=None, max_length=256, description="Existing user session ID."),
    ]


@router.post("/")
@limiter.limit(request_limit)
async def chat_stream(
    request: Request, body: ChatRequest, user_id: str = Depends(get_current_user)
):
    """
    Handles chat messages, checks authentication status, and streams
    Agent Engine responses back to the client.
    """
    logger.info(f"Received chat request from {user_id}")

    missing_providers = check_missing_providers(user_id)

    if missing_providers:
        logger.warning(f"User {user_id} is missing tokens for: {missing_providers}")

        async def auth_required_stream():
            event = {
                "type": "AUTH_REQUIRED",
                "missing_providers": missing_providers,
                "message": "Please authenticate with the required data sources before continuing.",
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(auth_required_stream(), media_type="text/event-stream")

    if not remote_app:
        raise HTTPException(
            status_code=500, detail="Agent Engine is not configured or unreachable."
        )

    # 2. AGENT EXECUTION
    # Create session if not provided
    session_id = body.session_id
    if not session_id:
        remote_session = await remote_app.async_create_session(user_id=user_id)
        session_id = remote_session["id"]
        logger.info(f"Created new session {session_id} for user {user_id}")

    async def generate_agent_stream():
        # First event to let the frontend know the session_id
        yield f"data: {json.dumps({'type': 'session_info', 'session_id': session_id})}\n\n"

        try:
            async for event in remote_app.async_stream_query(
                user_id=user_id,
                session_id=session_id,
                message=body.message,
            ):
                # The event from async_stream_query is a dict, we need to pass it safely to JSON
                yield f"data: {json.dumps({'type': 'agent_event', 'payload': event})}\n\n"
        except Exception:  # noqa: BLE001 - Convert SDK failures into the existing SSE error event
            logger.error("Agent streaming failed")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred during agent streaming. Please try again later.'})}\n\n"

    return StreamingResponse(generate_agent_stream(), media_type="text/event-stream")
