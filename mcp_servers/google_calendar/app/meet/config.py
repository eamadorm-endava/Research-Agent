from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MeetRootConfig(BaseSettings):
    """Shared immutable configuration base for the Meet module."""

    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        env_file_encoding="utf-8",
    )


class MeetConfig(MeetRootConfig):
    """Configuration for Google Meet API and defaults."""

    meet_api_service_name: Annotated[
        str,
        Field(
            default="meet",
            description="Google API discovery service name for Meet.",
        ),
    ]
    meet_api_version: Annotated[
        str,
        Field(
            default="v2",
            description="Google Meet API version.",
        ),
    ]
    space_name_prefix: Annotated[
        str,
        Field(
            default="spaces/",
            description="Prefix used for Google Meet space resource names.",
        ),
    ]


MEET_CONFIG = MeetConfig()
