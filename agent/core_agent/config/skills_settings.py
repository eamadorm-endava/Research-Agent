from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class SkillBaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )
    """
    Base generic config representing any skill path that can be loaded by adk.
    """
    pass


class MeetingSummarySkillConfig(SkillBaseConfig):
    SKILL_NAME: Annotated[str, Field(default="meeting-summary")]
    FOLDER: Annotated[
        str,
        Field(
            default="AI Meetings Summaries",
            description="Folder where meeting summaries are stored in Drive",
            validation_alias="MEETING_SUMMARY_FOLDER",  # validation_alias is used to map the environment variable to the field
        ),
    ]
    FILENAME_PATTERN: Annotated[
        str,
        Field(
            default="YYYY-MM-DD - meeting-name - Summary.docx",
            description="Pattern used to name generated meeting summary documents",
            validation_alias="MEETING_SUMMARY_FILENAME_PATTERN",  # validation_alias is used to map the environment variable to the field
        ),
    ]
