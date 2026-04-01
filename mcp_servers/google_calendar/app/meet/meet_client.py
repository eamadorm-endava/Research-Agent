from typing import Any
from loguru import logger
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import MEET_CONFIG
from .schemas import (
    ArtifactStatus,
    ConferenceAttendee,
    ConferenceSession,
    Recording,
    RecordingsMetadata,
    Transcript,
    TranscriptsMetadata,
    UserType,
)


class MeetClient:
    """Specialized client for Google Meet API v2 interactions.

    Provides tiered access to conference records, participants, and artifacts.
    """

    def __init__(self, creds: Credentials) -> None:
        """Initializes the MeetClient with Google API credentials for V2 access.

        Sets up the underlying Google API discovery service for Meet conference records.
        This client provides high-level abstractions for managing sessions and artifacts.

        Args:
            creds (Credentials): Authorized Google OAuth2 credentials object.
        """
        self.creds = creds
        self.meet = build(
            MEET_CONFIG.meet_api_service_name,
            MEET_CONFIG.meet_api_version,
            credentials=creds,
            cache_discovery=False,
        )
        logger.info(f"Initialized MeetClient ({MEET_CONFIG.meet_api_version})")

    # --- Public Methods (Tiered API) ---

    def list_conference_sessions(self, conference_id: str) -> list[ConferenceSession]:
        """Lists and summarizes all conference sessions associated with a specific conference ID.

        Resolves the conference ID to a canonical space name and fetches all historical
        conference records. Each session is enriched with recording and transcript metadata.

        Args:
            conference_id (str): The 10-letter Google Meet code (e.g., 'abc-defg-hij').

        Returns:
            list[ConferenceSession]: A list of objects summarizing each session found.
        """
        logger.info(f"Listing sessions for conference ID: {conference_id}")

        space_name = self._resolve_space_name(conference_id)
        if not space_name:
            logger.warning(f"Could not resolve space for ID: {conference_id}")
            return []

        raw_records = self._fetch_conference_records(space_name)
        sessions = []

        for raw_record in raw_records:
            record_name = raw_record.get("name")
            logger.debug(f"Enriching session summary for record: {record_name}")

            # Fetch summary counts and IDs for nested metadata
            recordings = self._fetch_recordings(record_name)
            transcripts = self._fetch_transcripts(record_name)
            participants = self._fetch_participants(record_name)

            session = ConferenceSession(
                conference_session_id=record_name,
                start_time=raw_record.get("startTime"),
                end_time=raw_record.get("endTime"),
                total_participants=len(participants),
                recordings=RecordingsMetadata(
                    total_recordings=len(recordings),
                    recording_ids=[r.get("name") for r in recordings],
                ),
                transcripts=TranscriptsMetadata(
                    total_transcripts=len(transcripts),
                    transcript_ids=[t.get("name") for t in transcripts],
                ),
            )
            sessions.append(session)

        logger.info(f"Retrieved {len(sessions)} sessions for {conference_id}")
        return sessions

    def get_participants_info(
        self, conference_session_id: str
    ) -> list[ConferenceAttendee]:
        """Retrieves and maps detailed atomic participant data for a specific conference session.

        Queries the Meet API for all participants associated with the given session ID.
        It handles different user types (signed-in, anonymous, phone) and maps them to models.

        Args:
            conference_session_id (str): Canonical resource ID (e.g., 'conferenceRecords/abc-123').

        Returns:
            list[ConferenceAttendee]: A list of attendees with their join/leave times and metadata.
        """
        logger.info(
            f"Fetching detailed participants for session: {conference_session_id}"
        )
        raw_participants = self._fetch_participants(conference_session_id)

        attendees = [
            self._map_attendee(raw_participant) for raw_participant in raw_participants
        ]
        logger.debug(
            f"Mapped {len(attendees)} participants for {conference_session_id}"
        )
        return attendees

    def get_recording_info(self, recording_id: str) -> Recording:
        """Retrieves detailed atomic metadata for a specific Google Meet recording artifact.

        Fetches the recording resource directly from the Meet API using its unique ID.
        This includes the Drive file ID and state of the media generation.

        Args:
            recording_id (str): The resource ID (e.g., 'conferenceRecords/abc/recordings/xyz').

        Returns:
            Recording: A model containing the recording metadata, URL, and duration.
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

    def get_transcript_info(self, transcript_id: str) -> Transcript:
        """Retrieves detailed atomic metadata for a specific Google Meet transcript artifact.

        Fetces the transcript resource from the API, providing access to the Docs ID.
        Transcripts represent a structured log of the meeting conversation.

        Args:
            transcript_id (str): The canonical resource ID of the transcript.

        Returns:
            Transcript: A model containing transcript status and the Google Docs link.
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

    def _resolve_space_name(self, conference_id: str) -> str:
        """Resolves a human-readable 10-letter conference ID to its canonical space name.

        Uses the spaces.get endpoint to verify the existsnce of the meeting and
        retrieve its official internal identifier used for record lookup.

        Args:
            conference_id (str): The ID of the meeting (e.g., 'abc-defg-hij').

        Returns:
            str: The resolved space name (e.g., 'spaces/abcdefg') or an empty string.
        """
        alias = f"spaces/{conference_id}"
        try:
            logger.debug(f"Resolving space for conference ID: {conference_id}")
            space = self.meet.spaces().get(name=alias).execute()
            return space.get("name")
        except HttpError as exc:
            logger.warning(f"Could not resolve space {conference_id}: {exc}")
            return ""

    def _fetch_conference_records(self, space_name: str) -> list[dict[str, Any]]:
        """Queries the Google Meet API for all historical records associated with a space.

        Retrieves conference sessions using a filter string to target specific spaces.
        This identifies individual session instances of a recurring or single meeting.

        Args:
            space_name (str): The canonical name of the space to filter records for.

        Returns:
            list[dict[str, Any]]: A list of raw conferenceRecord dictionaries from the API.
        """
        try:
            logger.debug(f"Fetching sessions for space: {space_name}")
            # Filter by space ensures we only get records for this specific meeting code
            filter_str = f'space.name="{space_name}"'
            response = self.meet.conferenceRecords().list(filter=filter_str).execute()
            return response.get("conferenceRecords", [])
        except HttpError as exc:
            logger.error(f"Error listing conference records: {exc}")
            return []

    def _fetch_recordings(self, record_name: str) -> list[dict[str, Any]]:
        """Fetches the raw list of all recording artifacts associated with a session name.

        Iterates through the recordings child collection of a specific conference record.
        Recordings may take time to generate and might appear empty shortly after a session.

        Args:
            record_name (str): The resource name of the parent session.

        Returns:
            list[dict[str, Any]]: A list of raw recording dictionaries from the API.
        """
        try:
            response = (
                self.meet.conferenceRecords()
                .recordings()
                .list(parent=record_name)
                .execute()
            )
            return response.get("recordings", [])
        except HttpError:
            return []

    def _fetch_transcripts(self, record_name: str) -> list[dict[str, Any]]:
        """Fetches the raw list of transcript artifacts generated during a conference session.

        Looks up available transcripts within the specified conference record name.
        Each transcript typically points to a unique Google Docs document.

        Args:
            record_name (str): The resource name of the parent session.

        Returns:
            list[dict[str, Any]]: A list of raw transcript dictionaries from the API.
        """
        try:
            response = (
                self.meet.conferenceRecords()
                .transcripts()
                .list(parent=record_name)
                .execute()
            )
            return response.get("transcripts", [])
        except HttpError:
            return []

    def _fetch_participants(self, record_name: str) -> list[dict[str, Any]]:
        """Retrieves raw participant metadata for everyone who joined a specific session.

        Fetches all participant resources for the given record name. This contains
        atomic join/leave timestamps and user identity information.

        Args:
            record_name (str): The resource name of the parent session.

        Returns:
            list[dict[str, Any]]: A list of raw participant dictionaries from the API.
        """
        try:
            response = (
                self.meet.conferenceRecords()
                .participants()
                .list(parent=record_name)
                .execute()
            )
            return response.get("participants", [])
        except HttpError:
            return []

    # --- Private Methods (Mapping) ---

    def _map_attendee(self, raw_participant_data: dict[str, Any]) -> ConferenceAttendee:
        """Transforms raw API participant data into a structured ConferenceAttendee model.

        Identifies the user type (Signed-in, Anonymous, or Phone) and extracts
        the display name and join/leave times while ignoring internal API fields.

        Args:
            raw_participant_data (dict[str, Any]): The raw dictionary from the participants.list API call.

        Returns:
            ConferenceAttendee: An initialized attendee model with descriptive attributes.
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

        return ConferenceAttendee(
            user_id=user_id or "ANONYMOUS",
            email=None,  # Not provided directly by Meet V2
            display_name=display_name,
            first_join_time=raw_participant_data.get("earliestStartTime"),
            last_leave_time=raw_participant_data.get("latestEndTime"),
            user_type=user_type,
        )

    def _map_recording(self, raw_recording_data: dict[str, Any]) -> Recording:
        """Converts raw recording artifact metadata into a structured Recording model.

        Extracts the Drive destination ID and ensures the status is mapped correctly
        to our internal ArtifactStatus enumeration for consistency.

        Args:
            raw_recording_data (dict[str, Any]): The raw dictionary from the recording API.

        Returns:
            Recording: A structured model containing the recording's life cycle details.
        """
        drive_id = raw_recording_data.get("driveDestination", {}).get("file")
        return Recording(
            name=raw_recording_data.get("name"),
            state=ArtifactStatus(raw_recording_data.get("state", "STATE_UNSPECIFIED")),
            drive_file_id=drive_id,
            start_time=raw_recording_data.get("startTime"),
            end_time=raw_recording_data.get("endTime"),
        )

    def _map_transcript(self, raw_transcript_data: dict[str, Any]) -> Transcript:
        """Transforms raw transcript metadata into a structured Transcript model instance.

        Identifies the Google Docs destination for the generated transcript files
        and ensures technical start/end times are correctly mapped to model fields.

        Args:
            raw_transcript_data (dict[str, Any]): The raw dictionary from the transcript API.

        Returns:
            Transcript: A validated model summarizing the transcript artifact.
        """
        docs_id = raw_transcript_data.get("docsDestination", {}).get("document")
        return Transcript(
            name=raw_transcript_data.get("name"),
            state=ArtifactStatus(raw_transcript_data.get("state", "STATE_UNSPECIFIED")),
            docs_document_id=docs_id,
            start_time=raw_transcript_data.get("startTime"),
            end_time=raw_transcript_data.get("endTime"),
        )
