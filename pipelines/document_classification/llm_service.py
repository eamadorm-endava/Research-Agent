from google import genai
from google.genai import types
from pydantic import BaseModel
import json
from loguru import logger
from .config import EKB_CONFIG


class ClassificationResult(BaseModel):
    """Schema for document classification and summary."""

    domain: str
    tier: str
    description: str


class LLMService:
    """Service class for contextual document classification and summary generation.

    Uses Gemini 2.5 Flash to read documents from GCS URIs using ADC and
    Structured Output (JSON mode) via Pydantic schemas.
    """

    def __init__(self, project_id: str = EKB_CONFIG.PROJECT_ID):
        """Initializes the GenAI Client for Vertex AI using ADC.

        Args:
            project_id (str): The GCP project ID.
        """
        self.client = genai.Client(
            vertexai=True, project=project_id, location=EKB_CONFIG.LOCATION
        )
        # Using Gemini 2.5 Flash as requested for advanced multimodal analysis
        self.model_id = "gemini-2.5-flash"

    def classify_and_summarize(
        self, gcs_uri: str, mime_type: str, known_tier: str = None
    ) -> dict:
        """Analyzes a document to determine its domain, tier, and summary.

        Args:
            gcs_uri (str): URI of the document in GCS.
            mime_type (str): The MIME type of the document (e.g., application/pdf).
            known_tier (str, optional): The tier if already identified by DLP (4 or 5).

        Returns:
            dict: A dictionary containing 'domain', 'tier', and 'description'.
        """
        logger.info(
            f"Sending document to Gemini ({self.model_id}) with Structured Output."
        )

        prompt = f"""
        Analyze the attached document and provide the required metadata.
        
        Rules:
        - Domain: Must be one of {EKB_CONFIG.DOMAINS}.
        - Security Tier: If not provided, choose: 1-public, 2-internal, or 3-client-confidential.
        - Description: A single-paragraph summary, max 150 words.
        
        Context:
        Known Tier: {known_tier if known_tier else "Evaluate based on content (1-3)"}
        """

        # Implement simplified exponential backoff for 429 errors
        max_retries = 3
        base_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                contents = [
                    prompt,
                    types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type),
                ]

                # Use Pydantic schema for strict JSON compliance and reduction of 400 errors
                generate_config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ClassificationResult,
                    temperature=0.1,
                )

                response = self.client.models.generate_content(
                    model=self.model_id, contents=contents, config=generate_config
                )

                # The SDK returns a parsed object if response_schema is provided,
                # but we convert back to dict for consistency with the orchestrator.
                result = response.parsed
                if hasattr(result, "model_dump"):
                    result = result.model_dump()
                elif not isinstance(result, dict):
                    # Fallback to manual parsing if parsed is not available/working
                    result = json.loads(response.text)

                logger.info(f"Enrichment for {self.model_id} completed successfully.")
                return result

            except Exception as e:
                # Catch 429 RESOURCE_EXHAUSTED
                is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)

                if is_rate_limit and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Quota exhausted (429). Retrying in {delay}s... (Attempt {attempt + 1}/{max_retries})"
                    )
                    import time

                    time.sleep(delay)
                    continue

                logger.error(f"Error calling Google Gen AI ({self.model_id}): {str(e)}")
                # Diagnostics: attempt to log response details if it's a ClientError
                if hasattr(e, "message"):
                    logger.error(f"Detailed message: {e.message}")
                raise
