from pydantic import BaseModel, Field
from typing import Annotated, Literal


class ContextualClassificationResponse(BaseModel):
    """Schema for the response of the Gemini contextual classification."""

    final_classification_tier: Annotated[
        int, Field(description="The definitive security tier (1-5).", ge=1, le=5)
    ]
    confidence: Annotated[
        float,
        Field(
            description="The model's confidence in its classification (0.0 - 1.0).",
            ge=0.0,
            le=1.0,
        ),
    ]
    final_domain: Annotated[
        Literal["it", "finance", "hr", "sales", "executives", "legal", "operations"],
        Field(description="The validated target business domain."),
    ]
    file_description: Annotated[
        str, Field(description="A brief summary of the document, less than 150 words.")
    ]
