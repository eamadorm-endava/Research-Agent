from __future__ import annotations

from typing import Any, Optional
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .calendar_client import CalendarClient
from .drive_client import DriveClient
from .config import MEET_CONFIG, CALENDAR_CONFIG
from .schemas import (
    AuthenticationError,
    ConferenceRecordModel,
    MeetApiQuotaError,
    ParticipantModel,
    RecordingModel,
    TranscriptEntryModel,
    TranscriptModel,
)

logger = logging.getLogger(__name__)


class MeetClient:
    """Stateless connector for Google Meet API.

    This client uses the ``google-api-python-client`` discovery service to
    interact with Google Meet conference records and associated artifacts.
    It utilizes auxiliary Drive and Calendar clients to fetch extra metadata.
    """

    def __init__(self, creds: Credentials) -> None:
        self.creds = creds
        self.meet = build(
            MEET_CONFIG.meet_api_service_name,
            MEET_CONFIG.meet_api_version,
            credentials=creds,
            cache_discovery=False,
        )
        self.calendar_client = CalendarClient(creds)
        self.drive_client = DriveClient(creds)
        logger.info(
            f"Initialized MeetClient with Meet ({MEET_CONFIG.meet_api_version})"
        )

    def _build_conference_filter(
        self,
        start_date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_date: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> str:
        """Build a Meet API filter string from date and time components.

        Args:
            start_date (str | None): Starting date in YYYY-MM-DD format.
            start_time (str | None): Starting time in HH:MM:SSZ format.
            end_date (str | None): Ending date in YYYY-MM-DD format.
            end_time (str | None): Ending time in HH:MM:SSZ format.

        Returns:
            str: A concatenated filter string for the Meet API.
        """
        logger.debug(
            f"Building filter with start_date={start_date}, start_time={start_time}, end_date={end_date}, end_time={end_time}"
        )
        filter_parts: list[str] = []

        if start_date:
            full_start = (
                f"{start_date}T{start_time or CALENDAR_CONFIG.default_start_time}"
            )
            filter_parts.append(f'start_time>="{full_start}"')

        if end_date:
            full_end = f"{end_date}T{end_time or CALENDAR_CONFIG.default_end_time}"
            filter_parts.append(f'start_time<="{full_end}"')

        filter_str = " AND ".join(filter_parts)
        logger.debug(f"Generated filter string: {filter_str}")
        return filter_str

    def list_meetings(
        self,
        max_results: int = MEET_CONFIG.default_page_size,
        conference_name: Optional[str] = None,
        event_status: Optional[str] = None,
        start_date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_date: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> list[ConferenceRecordModel]:
        """List past and active conference records visible to the caller.

        Records are automatically enriched with titles and descriptions from linked Google
        Calendar events where possible.

        Args:
            max_results (int): Maximum number of records to return.
            conference_name (str | None): A flexible search for the meeting title.
            event_status (str | None): Filter by the caller's response status.
            start_date (str | None): Starting date (YYYY-MM-DD).
            start_time (str | None): Starting time (HH:MM:SSZ).
            end_date (str | None): Ending date (YYYY-MM-DD).
            end_time (str | None): Ending time (HH:MM:SSZ).

        Returns:
            list[ConferenceRecordModel]: A list of enriched conference records.

        Raises:
            AuthenticationError: If the API returns 401 or 403.
            MeetApiQuotaError: If the API returns 429.
        """
        logger.info(
            f"Listing meetings (max_results={max_results}, name_filter={conference_name}, status_filter={event_status})"
        )
        filter_parts: list[str] = []

        # 1. Calendar search for meeting codes if name or status is provided
        if conference_name or event_status:
            codes = self.calendar_client.find_meeting_ids(
                conference_name=conference_name, event_status=event_status
            )
            if codes:
                code_filters = [f"space.meeting_code='{c}'" for c in codes]
                filter_parts.append(f"({' OR '.join(code_filters)})")
            else:
                logger.info("No matching meetings found in Calendar search.")
                return []

        # 2. Build time-range filters
        range_filter = self._build_conference_filter(
            start_date=start_date,
            start_time=start_time,
            end_date=end_date,
            end_time=end_time,
        )
        if range_filter:
            filter_parts.append(range_filter)

        kwargs: dict[str, Any] = {
            "pageSize": min(max_results, MEET_CONFIG.max_page_size)
        }
        if filter_parts:
            kwargs["filter"] = " AND ".join(filter_parts)

        logger.debug(f"Calling Meet API list_meetings with kwargs: {kwargs}")

        try:
            response = self.meet.conferenceRecords().list(**kwargs).execute()
        except HttpError as exc:
            _raise_for_status(exc)

        records = response.get("conferenceRecords", [])
        models = [ConferenceRecordModel.model_validate(r) for r in records]
        logger.info(f"Found {len(models)} conference records in Meet API")

        # 3. Enrich records with Calendar titles and descriptions
        for model in models:
            if model.space and model.startTime:
                meeting_code = model.space.replace(MEET_CONFIG.space_name_prefix, "")

                # Fetch the actual Space resource to find the canonical meeting code
                try:
                    space_details = self.meet.spaces().get(name=model.space).execute()
                    meeting_uri = space_details.get("meetingUri", "")
                    if meeting_uri:
                        meeting_code = meeting_uri.split("/")[-1]
                except HttpError:
                    logger.debug(f"Could not retrieve space details for {model.space}")

                # Fetch event details using CalendarClient
                details = self.calendar_client.get_event_details_by_meeting_code(
                    meeting_code=meeting_code, start_time_iso=model.startTime
                )
                if details:
                    model.title = details.get("title")
                    model.description = details.get("description")

        return models

    def list_recordings(
        self,
        conference_record_name: str,
    ) -> list[RecordingModel]:
        """
        List all recordings for a specific conference record.

        Args:
            conference_record_name (str): The resource name of the conference record.

        Returns:
            list[RecordingModel]: A list of recording models associated with the meeting.
        """
        logger.info(f"Listing recordings for {conference_record_name}")
        try:
            logger.debug(
                f"Calling Meet API list_recordings for {conference_record_name}"
            )
            response = (
                self.meet.conferenceRecords()
                .recordings()
                .list(parent=conference_record_name)
                .execute()
            )
        except HttpError as exc:
            _raise_for_status(exc)

        recordings = response.get("recordings", [])
        models = [RecordingModel.model_validate(r) for r in recordings]
        logger.info(f"Found {len(models)} recordings")
        return models

    def list_transcripts(
        self,
        conference_record_name: str,
    ) -> list[TranscriptModel]:
        """
        List all transcripts for a specific conference record.

        Args:
            conference_record_name (str): The resource name of the conference record.

        Returns:
            list[TranscriptModel]: A list of transcript models associated with the meeting.
        """
        logger.info(f"Listing transcripts for {conference_record_name}")
        try:
            logger.debug(
                f"Calling Meet API list_transcripts for {conference_record_name}"
            )
            response = (
                self.meet.conferenceRecords()
                .transcripts()
                .list(parent=conference_record_name)
                .execute()
            )
        except HttpError as exc:
            _raise_for_status(exc)

        transcripts = response.get("transcripts", [])
        models = [TranscriptModel.model_validate(t) for t in transcripts]
        logger.info(f"Found {len(models)} transcripts")
        return models

    def list_transcript_entries(
        self,
        transcript_name: str,
        page_size: int = MEET_CONFIG.default_page_size,
    ) -> list[TranscriptEntryModel]:
        """
        List entries (dialogue) for a specific transcript.

        Args:
            transcript_name (str): The resource name of the transcript.
            page_size (int): The number of entries to fetch per page.

        Returns:
            list[TranscriptEntryModel]: A list of transcript entries.
        """
        logger.info(f"Listing transcript entries for {transcript_name}")
        try:
            logger.debug(
                f"Calling Meet API list_transcript_entries for {transcript_name} with page_size={page_size}"
            )
            response = (
                self.meet.conferenceRecords()
                .transcripts()
                .entries()
                .list(
                    parent=transcript_name,
                    pageSize=min(page_size, MEET_CONFIG.max_page_size),
                )
                .execute()
            )
        except HttpError as exc:
            _raise_for_status(exc)

        entries = response.get("transcriptEntries", [])
        models = [TranscriptEntryModel.model_validate(e) for e in entries]
        logger.info(f"Found {len(models)} transcript entries")
        return models

    def list_participants(
        self,
        conference_record_name: str,
    ) -> list[ParticipantModel]:
        """
        List all participants for a specific conference record.

        Args:
            conference_record_name (str): The resource name of the conference record.

        Returns:
            list[ParticipantModel]: A list of participant models.
        """
        logger.info(f"Listing participants for {conference_record_name}")
        try:
            logger.debug(
                f"Calling Meet API list_participants for {conference_record_name}"
            )
            response = (
                self.meet.conferenceRecords()
                .participants()
                .list(parent=conference_record_name)
                .execute()
            )
        except HttpError as exc:
            _raise_for_status(exc)

        participants = response.get("participants", [])
        models = [ParticipantModel.model_validate(p) for p in participants]
        logger.info(f"Found {len(models)} participants")
        return models


def build_meet_credentials(
    access_token: Optional[str] = None,
) -> Credentials:
    """
    Build a Google Credentials object from an access token.

    Args:
        access_token (str | None): The OAuth access token string.

    Returns:
        Credentials: A Google Credentials object initialized with the token.
    """
    if access_token:
        logger.debug("Building credentials from provided access token.")
        return Credentials(token=access_token)

    logger.error("No access token provided to build meet credentials.")
    raise RuntimeError(
        "No Meet credentials available. Provide a delegated user access token header."
    )


def _raise_for_status(exc: HttpError) -> None:
    """
    Handle Google API HttpError and raise specific custom exceptions based on status code.

    Args:
        exc (HttpError): The original HttpError raised by the Google API client.

    Returns:
        None: This function always raises an exception.
    """
    status = exc.resp.status if exc.resp else None
    if status in (401, 403):
        logger.error(f"Authentication failed with status {status}: {exc}")
        raise AuthenticationError(
            f"Google Meet API authentication failed ({status}): {exc}"
        ) from exc
    if status == 429:
        logger.warning(f"Quota exceeded: {exc}")
        raise MeetApiQuotaError(f"Google Meet API quota exceeded: {exc}") from exc
    logger.error(f"Unhandled Google API HTTP error ({status}): {exc}")
    raise exc
