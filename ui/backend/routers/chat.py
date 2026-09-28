import json
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from .oauth import get_current_user

# In a real scenario, this would use vertexai SDK
# e.g., from vertexai.preview import reasoning_engines
# For now, we mock the stream to demonstrate the architecture
from vertexai import agent_engines
import vertexai

from agent.core_agent.security.token_store import token_store
from agent.core_agent.config import GCP_CONFIG
from ..config import UI_CONFIG

router = APIRouter()

# Initialize Vertex AI
vertexai.init(project=GCP_CONFIG.PROJECT_ID, location=GCP_CONFIG.REGION)

# Initialize the remote app globally to reuse the connection
try:
    remote_app = agent_engines.get(UI_CONFIG.AGENT_RESOURCE_NAME)
    logger.info(
        f"Successfully connected to remote agent engine: {UI_CONFIG.AGENT_RESOURCE_NAME}"
    )
except Exception as e:
    logger.error(f"Failed to connect to agent engine. Is the ID correct? Error: {e}")
    remote_app = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


# Re-use the IAP header extraction


def check_missing_providers(user_id: str) -> list[str]:
    """Checks which required data source tokens are missing for the user."""
    required_providers = ["google", "microsoft", "atlassian"]
    missing = []

    for provider in required_providers:
        token = token_store.get_valid_access_token(user_id=user_id, provider=provider)
        if not token:
            missing.append(provider)

    return missing


@router.post("/")
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
                # E.g. event could be FunctionCall, string chunk, etc. depending on ADK stream format
                yield f"data: {json.dumps({'type': 'agent_event', 'payload': event})}\n\n"
        except Exception as e:
            logger.error(f"Error during agent streaming: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate_agent_stream(), media_type="text/event-stream")
