from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class CloudTasksConfig(BaseSettings):
    """Configuration class for the Cloud Tasks integration."""

    model_config = SettingsConfigDict(
        env_file=[".env", "../../.env", "../../../.env", "../../../../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TASKS_QUEUE_ID: Annotated[
        str,
        Field(
            default="ekb-ingestion-queue",
            description="The Cloud Tasks queue ID for decoupling background ingestion.",
        ),
    ]

    TASKS_LOCATION: Annotated[
        str,
        Field(
            default="us-central1",
            description="The GCP location for the Cloud Tasks queue.",
        ),
    ]

    SERVICE_ACCOUNT_EMAIL: Annotated[
        str,
        Field(
            default="",
            description="The service account email to use for authenticated Cloud Tasks invocations.",
        ),
    ]


CLOUD_TASKS_CONFIG = CloudTasksConfig()
