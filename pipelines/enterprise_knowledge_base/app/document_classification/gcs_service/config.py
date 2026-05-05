from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Annotated


class GCSConfig(BaseSettings):
    """Configuration for GCS service operations and resilience."""

    model_config = SettingsConfigDict(
        env_prefix="GCS_",
        env_file=".env",
        extra="ignore",
    )

    MAX_RETRIES: Annotated[
        int,
        Field(
            default=3,
            description="Maximum number of retry attempts for GCS operations.",
        ),
    ]

    BASE_DELAY: Annotated[
        int,
        Field(
            default=2,
            description="Base delay in seconds for exponential backoff calculation.",
        ),
    ]


# Global instance for easy access within the gcs_service package
gcs_config = GCSConfig()
