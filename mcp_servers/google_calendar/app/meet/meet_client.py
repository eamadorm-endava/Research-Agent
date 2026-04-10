from typing import Union
from loguru import logger
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import MEET_CONFIG
from .schemas import (
    ArtifactStatus,
    MeetParticipant,
    MeetSession,
    MeetRecording,
    MeetRecordingsSummary,
    MeetTranscript,
    MeetTranscriptsSummary,
    UserType,
)


class MeetClient:
    """Specialized client for Google Meet API v2 interactions.

    Provides tiered access to Meet sessions, participants, and artifacts (recordings/transcripts).
    """

    def __init__(self, creds: Credentials) -> None:
        """Initializes the MeetClient with Google API credentials for V2 access.

        Sets up the underlying Google API discovery service for Meet sessions.
        This client provides high-level abstractions for managing sessions and artifacts.

        Args:
            creds (Credentials): Authorized Google OAuth2 credentials object.
        """
        self.meet = build(
            MEET_CONFIG.meet_api_service_name,
            MEET_CONFIG.meet_api_version,
            credentials=creds,
            cache_discovery=False,
        )
        logger.info(f"Initialized MeetClient ({MEET_CONFIG.meet_api_version})")

    # --- Public Methods (Tiered API) ---

    def list_meet_sessions(self, meeting_code: str) -> list[MeetSession]:
        """Lists and summarizes all Meet sessions associated with a specific meeting code.

        Resolves the meeting code (10-letter ID) to a canonical space name and fetches
        all historical session records. Each session is enriched with recording and
        transcript summaries.

        Note: Meet sessions are registered whenever a user joins a meeting space,
        even if they do not stay for the full duration.

        Args:
            meeting_code (str): The 10-letter Google Meet code (e.g., 'abc-defg-hij').

        Returns:
            list[MeetSession]: A list of structured models summarizing each meeting session.
        """
        logger.info(f"Listing sessions for meeting code: {meeting_code}")

        space_name = self._resolve_space_name(meeting_code)
        if not space_name:
            logger.warning(f"Could not resolve space for meeting code: {meeting_code}")
            return []

        raw_records = self._fetch_meet_sessions(space_name)
        sessions = []

        for raw_record in raw_records:
            meet_session_id = raw_record.get("name")
            logger.debug(f"Enriching session summary for record: {meet_session_id}")

            # Fetch participants for all sessions
            participants = self._fetch_participants(meet_session_id)

            # Skip empty sessions where no participants ever joined
            if not participants:
                logger.debug(f"Skipping empty session record: {meet_session_id}")
                continue

            # Fetch recordings and transcripts for only non-empty sessions
            recordings = self._fetch_recordings(meet_session_id)
            transcripts = self._fetch_transcripts(meet_session_id)

            session = MeetSession(
                meeting_code=meeting_code,
                session_id=meet_session_id,
                start_time=raw_record.get("startTime"),
                end_time=raw_record.get("endTime"),
                total_participants=len(participants),
                recordings=MeetRecordingsSummary(
                    total_recordings=len(recordings),
                    recording_ids=[r.get("name") for r in recordings],
                ),
                transcripts=MeetTranscriptsSummary(
                    total_transcripts=len(transcripts),
                    transcript_ids=[t.get("name") for t in transcripts],
                ),
            )
            sessions.append(session)

        logger.info(
            f"Retrieved {len(sessions)} sessions for meeting code {meeting_code}"
        )
        return sessions

    def list_meet_participants(self, meet_session_id: str) -> list[MeetParticipant]:
        """Retrieves and maps detailed participant data for a specific Meet session.

        Queries the Meet API for all participants associated with the given session ID.
        Identifies user types (Signed-in, Anonymous, Phone) and maps them to structured models.

        Args:
            meet_session_id (str): The unique Meet session ID (e.g., 'conferenceRecords/abc-123-xyz').

        Returns:
            list[MeetParticipant]: A list of participants with join/leave times and identity metadata.
        """
        logger.info(f"Fetching detailed participants for session: {meet_session_id}")
        raw_participants = self._fetch_participants(meet_session_id)

        attendees = [
            self._map_participant(raw_participant)
            for raw_participant in raw_participants
        ]
        logger.debug(f"Mapped {len(attendees)} participants for {meet_session_id}")
        return attendees

    def get_meet_recording(self, recording_id: str) -> MeetRecording:
        """Retrieves detailed metadata for a specific Google Meet recording.

        Fetches recording status, start/end times, and the associated Google Drive ID.

        Args:
            recording_id (str): The unique recording ID (e.g., 'conferenceRecords/abc/recordings/xyz').

        Returns:
            MeetRecording: A structured model containing the recording metadata.
        """
        logger.info(f"Fetching detailed recording metadata for: {recording_id}")
        try:
            raw_recording = (
                self.meet.conferenceRecords()
                .recordings()
                .get(name=recording_id)
                .execute()
            )
            return self._map_recording(raw_recording)
        except HttpError as exc:
            logger.error(f"Failed to fetch recording {recording_id}: {exc}")
            raise

    def get_meet_transcript(self, transcript_id: str) -> MeetTranscript:
        """Retrieves detailed metadata for a specific Google Meet transcript.

        Fetches transcript status and the associated Google Docs ID.

        Args:
            transcript_id (str): The canonical resource ID of the transcript.

        Returns:
            MeetTranscript: A model containing transcript metadata and status.
        """
        logger.info(f"Fetching detailed transcript metadata for: {transcript_id}")
        try:
            raw_transcript = (
                self.meet.conferenceRecords()
                .transcripts()
                .get(name=transcript_id)
                .execute()
            )
            return self._map_transcript(raw_transcript)
        except HttpError as exc:
            logger.error(f"Failed to fetch transcript {transcript_id}: {exc}")
            raise

    # --- Private Methods (Fetching) ---

    def _resolve_space_name(self, meeting_code: str) -> str:
        """Resolves a human-readable 10-letter meeting code to its canonical space name.

        Uses the spaces.get endpoint to verify the existsnce of the meeting and
        retrieve its official internal identifier used for record lookup.

        Args:
            meeting_code (str): The 10-letter meeting code (e.g., 'abc-defg-hij').

        Returns:
            str: The resolved space name (e.g., 'spaces/abcdefg') or an empty string.
        """
        alias = f"spaces/{meeting_code}"
        try:
            logger.debug(f"Resolving space for meeting code: {meeting_code}")
            space = self.meet.spaces().get(name=alias).execute()
            return space.get("name")
        except HttpError as exc:
            logger.warning(
                f"Could not resolve space for meeting code {meeting_code}: {exc}"
            )
            return ""

    def _fetch_meet_sessions(self, space_name: str) -> list[dict]:
        """Queries the Google Meet API for all historical records associated with a space.

        Retrieves Meet sessions using a filter string to target specific spaces.
        This identifies individual session instances of a recurring or single meeting.

        Args:
            space_name (str): The canonical name of the space to filter records for.

        Returns:
            list[dict[str, Any]]: A list of raw session record dictionaries from the API.
        """
        try:
            logger.debug(f"Fetching sessions for space: {space_name}")
            # Filter by space ensures we only get records for this specific meeting code
            filter_str = f'space.name="{space_name}"'
            response = self.meet.conferenceRecords().list(filter=filter_str).execute()
            return response.get("conferenceRecords", [])
        except HttpError as exc:
            logger.error(f"Error listing Meet sessions: {exc}")
            return []

    def _fetch_recordings(self, meet_session_id: str) -> list[dict]:
        """Fetches the raw list of all recording artifacts associated with a session ID.

        Iterates through the recordings child collection of a specific Meet session.
        Recordings may take time to generate and might appear empty shortly after a session.

        Args:
            meet_session_id (str): The unique ID of the parent session.

        Returns:
            list[dict[str, Any]]: A list of raw recording dictionaries from the API.
        """
        try:
            response = (
                self.meet.conferenceRecords()
                .recordings()
                .list(parent=meet_session_id)
                .execute()
            )
            return response.get("recordings", [])
        except HttpError:
            return []

    def _fetch_transcripts(self, meet_session_id: str) -> list[dict]:
        """Fetches the raw list of transcript artifacts generated during a Meet session.

        Looks up available transcripts within the specified session ID.
        Each transcript typically points to a unique Google Docs document.

        Args:
            meet_session_id (str): The unique ID of the parent session.

        Returns:
            list[dict[str, Any]]: A list of raw transcript dictionaries from the API.
        """
        try:
            response = (
                self.meet.conferenceRecords()
                .transcripts()
                .list(parent=meet_session_id)
                .execute()
            )
            return response.get("transcripts", [])
        except HttpError:
            return []

    def _fetch_participants(self, meet_session_id: str) -> list[dict]:
        """Retrieves raw participant metadata for everyone who joined a specific session.

        Fetches all participant resources for the given session ID. This contains
        atomic join/leave timestamps and user identity information.

        Args:
            meet_session_id (str): The unique ID of the parent session.

        Returns:
            list[dict[str, Any]]: A list of raw participant dictionaries from the API.
        """
        try:
            response = (
                self.meet.conferenceRecords()
                .participants()
                .list(parent=meet_session_id)
                .execute()
            )
            return response.get("participants", [])
        except HttpError:
            return []

    # --- Private Methods (Mapping) ---

    def _map_participant(
        self, raw_participant_data: dict[str, Union[str, list, dict]]
    ) -> MeetParticipant:
        """Transforms raw API participant data into a structured MeetParticipant model.

        Identifies the user type (Signed-in, Anonymous, or Phone) and extracts
        the display name and join/leave times while ignoring internal API fields.

        Args:
            raw_participant_data (dict[str, Any]): The raw dictionary from the participants.list API call.

        Returns:
            MeetParticipant: An initialized attendee model with descriptive attributes.
        """
        user_type = UserType.ANONYMOUS
        user_id = None
        display_name = "Unknown Participant"

        if "signedinUser" in raw_participant_data:
            user_type = UserType.SIGNED_IN
            # Resource name users/{user}
            user_id = raw_participant_data["signedinUser"].get("user")
            display_name = raw_participant_data["signedinUser"].get(
                "displayName", "Signed-in User"
            )
        elif "anonymousUser" in raw_participant_data:
            user_type = UserType.ANONYMOUS
            display_name = raw_participant_data["anonymousUser"].get(
                "displayName", "Guest"
            )
        elif "phoneUser" in raw_participant_data:
            user_type = UserType.PHONE
            display_name = raw_participant_data["phoneUser"].get(
                "displayName", "Phone caller"
            )

        return MeetParticipant(
            user_id=user_id or "ANONYMOUS",
            email=None,  # Not provided directly by Meet V2
            display_name=display_name,
            first_join_time=raw_participant_data.get("earliestStartTime"),
            last_leave_time=raw_participant_data.get("latestEndTime"),
            user_type=user_type,
        )

    def _map_recording(
        self, raw_recording_data: dict[str, Union[str, list, dict]]
    ) -> MeetRecording:
        """Converts raw recording artifact metadata into a structured MeetRecording model.

        Extracts the Drive destination ID and ensures the status is mapped correctly
        to our internal ArtifactStatus enumeration for consistency.

        Args:
            raw_recording_data (dict[str, Any]): The raw dictionary from the recording API.

        Returns:
            MeetRecording: A structured model containing the recording's life cycle details.
        """
        drive_id = raw_recording_data.get("driveDestination", {}).get("file")
        return MeetRecording(
            recording_id=raw_recording_data.get("name"),
            state=ArtifactStatus(raw_recording_data.get("state", "STATE_UNSPECIFIED")),
            drive_file_id=drive_id,
            start_time=raw_recording_data.get("startTime"),
            end_time=raw_recording_data.get("endTime"),
        )

    def _map_transcript(
        self, raw_transcript_data: dict[str, Union[str, list, dict]]
    ) -> MeetTranscript:
        """Transforms raw transcript metadata into a structured MeetTranscript model instance.

        Identifies the Google Docs destination for the generated transcript files
        and ensures technical start/end times are correctly mapped to model fields.

        Args:
            raw_transcript_data (dict[str, Any]): The raw dictionary from the transcript API.

        Returns:
            MeetTranscript: A validated model summarizing the transcript artifact.
        """
        docs_id = raw_transcript_data.get("docsDestination", {}).get("document")
        return MeetTranscript(
            transcript_id=raw_transcript_data.get("name"),
            state=ArtifactStatus(raw_transcript_data.get("state", "STATE_UNSPECIFIED")),
            docs_document_id=docs_id,
            start_time=raw_transcript_data.get("startTime"),
            end_time=raw_transcript_data.get("endTime"),
        )
