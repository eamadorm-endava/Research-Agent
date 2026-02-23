from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


class GCPConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )
    """
    Class that holds configuration values for GCP services. Allowing to, in any future, change the
    cloud provider or the way to access the secrets.
    """

    PROJECT_ID: Annotated[
        str,
        Field(
            default="dummy-gcp-project-id",
            description="GCP Project ID",
        ),
    ]
    REGION: Annotated[
        str,
        Field(
            default="dummy-gcp-region",
            description="GCP Region where most of the services will be deployed",
        ),
    ]


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
    )
    """
    Class that holds configuration values for the agent, it requires to assign
    parameters after initialization.
    """

    MODEL_NAME: Annotated[
        str,
        Field(
            default="gemini-2.5-flash",
            description="Name of the Gemini model to use.",
        ),
    ]
    TEMPERATURE: Annotated[
        float,
        Field(
            default=0.5,
            description="Controls randomness in model output: lower values make responses more focused, higher values more creative.",
            ge=0,
            le=1,
        ),
    ]
    TOP_P: Annotated[
        float,
        Field(
            default=0.95,
            description="Manage the randomness of the LLM ouput. Establish a probability threshold",
            ge=0,
            le=1,
        ),
    ]
    TOP_K: Annotated[
        float,
        Field(
            default=40,
            description="Determines how many of the most likely tokens should be considered when generating a response.",
        ),
    ]
    MAX_OUTPUT_TOKENS: Annotated[
        int,
        Field(
            default=10_000,
            description="Controls the maximum number of tokens generated in a single call to the LLM model",
        ),
    ]
    SEED: Annotated[
        int,
        Field(
            default=1080,
            description="If seed is set, the model makes a best effort to provide the same response for repeated requests. By default, a random number is used.",
        ),
    ]
    MODEL_ARMOR_TEMPLATE_ID: Annotated[
        str,
        Field(
            default="dummy-template-id",
            description="Model Armor Template ID",
        ),
    ]

