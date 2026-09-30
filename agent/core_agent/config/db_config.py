from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FirestoreConfig(BaseSettings):
    """
    Configuration settings for Firestore database connections.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
        env_prefix="FIRESTORE_",
    )

    DB_NAME: Annotated[
        str,
        Field(
            description="Name of the Firestore database",
            default="mock-firestore-database",
        ),
    ]
    COLLECTION_NAME: Annotated[
        str,
        Field(
            description="Name of the top-level collection", default="user_oauth_tokens"
        ),
    ]


FIRESTORE_CONFIG = FirestoreConfig()
