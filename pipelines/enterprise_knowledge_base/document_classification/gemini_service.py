import json
from typing import Optional
from google import genai
from google.genai import types
from loguru import logger
from .config import EKB_CONFIG
from .schemas import ContextualClassificationResponse


class GeminiService:
    """Service to interact with Gemini 2.5 Flash on Vertex AI."""

    def __init__(self) -> None:
        """Initializes the Vertex AI Gemini client."""
        self.client = genai.Client(
            vertexai=True,
            project=EKB_CONFIG.PROJECT_ID,
            location=EKB_CONFIG.GEMINI_LOCATION,
        )

    def classify_document(
        self,
        gcs_uri: str,
        mime_type: str,
        proposed_tier: Optional[int] = None,
        proposed_domain: Optional[str] = None,
        trust_level: Optional[str] = None,
    ) -> ContextualClassificationResponse:
        """Classifies a document using Gemini 2.5 Flash via GCS native access.

        Args:
            gcs_uri (str): GCS URI of the (potentially masked) document.
            mime_type (str): MIME type of the document.
            proposed_tier (Optional[int]): Tier suggested by Phase 1 (DLP).
            proposed_domain (Optional[str]): Domain proposed by the user/agent.
            trust_level (Optional[str]): Trust maturity level of the document.

        Returns:
            ContextualClassificationResponse: Structured classification result.
        """
        logger.info(f"Classifying document via Gemini: {gcs_uri}")
        system_prompt = self._build_system_prompt(
            proposed_tier, proposed_domain, trust_level
        )
        file_part = types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)

        response = self.client.models.generate_content(
            model=EKB_CONFIG.GEMINI_MODEL,
            contents=[system_prompt, file_part],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ContextualClassificationResponse,
            ),
        )

        # Parse the JSON response directly from the model output
        return ContextualClassificationResponse.model_validate(
            json.loads(response.text)
        )

    def _build_system_prompt(
        self,
        proposed_tier: Optional[int],
        proposed_domain: Optional[str],
        trust_level: Optional[str],
    ) -> str:
        """Constructs the system prompt with grounding context.

        Args:
            proposed_tier (Optional[int]): Tier from Phase 1.
            proposed_domain (Optional[str]): User-provided domain.
            trust_level (Optional[str]): User-provided trust level.

        Returns:
            str: The formatted system prompt.
        """
        prompt = "You are a Senior Security Architect. Classify this document based on the matrix:\n"
        prompt += EKB_CONFIG.CLASSIFICATION_MATRIX
        prompt += "\nContextual Grounding:\n"
        prompt += f"- Proposed Tier (DLP Phase 1): {proposed_tier or 'Unknown'}\n"
        prompt += f"- Proposed Domain: {proposed_domain or 'Unknown'}\n"
        prompt += f"- Trust Level: {trust_level or 'Unknown'}\n"
        prompt += f"- Valid Business Domains: {', '.join(EKB_CONFIG.VALID_DOMAINS)}\n\n"
        prompt += "Instructions:\n"
        prompt += "1. Return a JSON object with final_classification_tier (1-5).\n"
        prompt += "2. Return confidence (0.0-1.0).\n"
        prompt += f"3. Return final_domain (Must be one of: {', '.join(EKB_CONFIG.VALID_DOMAINS)}).\n"
        prompt += "4. Return file_description (brief summary, < 150 words).\n"
        return prompt
