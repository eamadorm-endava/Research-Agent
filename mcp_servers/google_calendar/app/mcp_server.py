import asyncio
import logging
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .config import CALENDAR_API_CONFIG, CALENDAR_SERVER_CONFIG
from .security import GoogleCalendarTokenVerifier, create_events_client
from .schemas import (
    GetMeetRecordingRequest,
    GetMeetRecordingResponse,
    GetMeetTranscriptRequest,
    GetMeetTranscriptResponse,
    ListCalendarEventsRequest,
    ListCalendarEventsResponse,
    ListMeetParticipantsRequest,
    ListMeetParticipantsResponse,
    ListMeetSessionsRequest,
    ListMeetSessionsResponse,
)


logger = logging.getLogger(__name__)

# Instantiate MCP Server
mcp = FastMCP(
    CALENDAR_SERVER_CONFIG.server_name,
    stateless_http=CALENDAR_SERVER_CONFIG.stateless_http,
    json_response=CALENDAR_SERVER_CONFIG.json_response,
    host=CALENDAR_SERVER_CONFIG.default_host,
    port=CALENDAR_SERVER_CONFIG.default_port,
    debug=CALENDAR_SERVER_CONFIG.debug,
    token_verifier=GoogleCalendarTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(CALENDAR_API_CONFIG.google_accounts_issuer_url),
        resource_server_url=AnyHttpUrl(
            f"http://{CALENDAR_SERVER_CONFIG.default_host}:{CALENDAR_SERVER_CONFIG.default_port}"
        ),
    ),
)


@mcp.tool()
async def list_calendar_events(
    request: ListCalendarEventsRequest,
) -> ListCalendarEventsResponse:
    """Fetch and parse calendar events into structured models.
    Retrieves events based on optional filters for date, time, and query terms.

    Args:
        request (ListCalendarEventsRequest): The request parameters.

    Returns:
        ListCalendarEventsResponse: A response containing the list of calendar events and execution status.
    """
    logger.info(
        "Tool call: list_calendar_events(max_events=%s, query=%s)",
        request.max_events,
        request.query,
    )
    try:
        client = create_events_client()
        events = await asyncio.to_thread(
            client.list_events,
            max_events=request.max_events,
            date_min=request.date_min,
            time_min=request.time_min,
            date_max=request.date_max,
            time_max=request.time_max,
            query=request.query,
        )
        return ListCalendarEventsResponse(
            execution_status="success",
            events=events,
        )
    except Exception as exc:
        logger.exception("Error listing calendar events")
        return ListCalendarEventsResponse(
            execution_status="error",
            execution_message=f"Error listing calendar events: {str(exc)}",
            events=[],
        )


@mcp.tool()
async def list_meet_sessions(
    request: ListMeetSessionsRequest,
) -> ListMeetSessionsResponse:
    """Lists and summarizes all Meet sessions for a specific meeting code.
    Identifies historical records for the specified 10-letter meeting ID.

    Args:
        request (ListMeetSessionsRequest): The request parameters containing the meeting code.

    Returns:
        ListMeetSessionsResponse: A response containing the Meet sessions and execution status.
    """
    logger.info("Tool call: list_meet_sessions(meeting_code=%s)", request.meeting_code)
    try:
        client = create_events_client()
        sessions = await asyncio.to_thread(
            client.list_meet_sessions, meeting_code=request.meeting_code
        )
        return ListMeetSessionsResponse(
            execution_status="success",
            meeting_code=request.meeting_code,
            sessions=sessions,
        )
    except Exception as exc:
        logger.exception("Error listing meet sessions")
        return ListMeetSessionsResponse(
            execution_status="error",
            execution_message=f"Error listing meet sessions: {str(exc)}",
            meeting_code=request.meeting_code,
            sessions=[],
        )


@mcp.tool()
async def list_meet_participants(
    request: ListMeetParticipantsRequest,
) -> ListMeetParticipantsResponse:
    """Retrieves detailed participant data for a specific Meet session.
    Lists join/leave times and identity metadata for everyone in the session.

    Args:
        request (ListMeetParticipantsRequest): The request parameters containing the session ID.

    Returns:
        ListMeetParticipantsResponse: A response containing the participants and execution status.
    """
    logger.info(
        "Tool call: list_meet_participants(meet_session_id=%s)", request.meet_session_id
    )
    try:
        client = create_events_client()
        participants = await asyncio.to_thread(
            client.list_meet_participants, meet_session_id=request.meet_session_id
        )
        return ListMeetParticipantsResponse(
            execution_status="success",
            meet_session_id=request.meet_session_id,
            participants=participants,
        )
    except Exception as exc:
        logger.exception("Error listing meet participants")
        return ListMeetParticipantsResponse(
            execution_status="error",
            execution_message=f"Error listing meet participants: {str(exc)}",
            meet_session_id=request.meet_session_id,
            participants=[],
        )


@mcp.tool()
async def get_meet_recording(
    request: GetMeetRecordingRequest,
) -> GetMeetRecordingResponse:
    """Retrieves detailed metadata for a specific Google Meet recording.
    Includes state, start/end times, and the associated Google Drive identifier.

    Args:
        request (GetMeetRecordingRequest): The request parameters containing the recording ID.

    Returns:
        GetMeetRecordingResponse: A response containing the recording metadata and execution status.
    """
    logger.info("Tool call: get_meet_recording(recording_id=%s)", request.recording_id)
    try:
        client = create_events_client()
        recording = await asyncio.to_thread(
            client.get_meet_recording, recording_id=request.recording_id
        )
        return GetMeetRecordingResponse(
            execution_status="success",
            recording_id=request.recording_id,
            recording=recording,
        )
    except Exception as exc:
        logger.exception("Error getting meet recording")
        return GetMeetRecordingResponse(
            execution_status="error",
            execution_message=f"Error getting meet recording: {str(exc)}",
            recording_id=request.recording_id,
            recording=None,
        )


@mcp.tool()
async def get_meet_transcript(
    request: GetMeetTranscriptRequest,
) -> GetMeetTranscriptResponse:
    """Retrieves detailed metadata for a specific Google Meet transcript.
    Includes state and the associated Google Docs document identifier.

    Args:
        request (GetMeetTranscriptRequest): The request parameters containing the transcript ID.

    Returns:
        GetMeetTranscriptResponse: A response containing the transcript metadata and execution status.
    """
    logger.info(
        "Tool call: get_meet_transcript(transcript_id=%s)", request.transcript_id
    )
    try:
        client = create_events_client()
        transcript = await asyncio.to_thread(
            client.get_meet_transcript, transcript_id=request.transcript_id
        )
        return GetMeetTranscriptResponse(
            execution_status="success",
            transcript_id=request.transcript_id,
            transcript=transcript,
        )
    except Exception as exc:
        logger.exception("Error getting meet transcript")
        return GetMeetTranscriptResponse(
            execution_status="error",
            execution_message=f"Error getting meet transcript: {str(exc)}",
            transcript_id=request.transcript_id,
            transcript=None,
        )
