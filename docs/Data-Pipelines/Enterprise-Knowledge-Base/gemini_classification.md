# Module: Gemini Contextual Classification (Phase 2)

## Overview
The `GeminiService` provides contextual intelligence to the document classification pipeline. While Phase 1 (Cloud DLP) handles deterministic pattern matching, Phase 2 uses **Gemini 2.5 Flash** to reason over document content and business metadata to arrive at a final security verdict.

## Key Features
- **Multimodal GCS Access**: Passes GCS URIs directly to the model using `fileData`/`fileUri`, avoiding unnecessary raw byte downloads.
- **Contextual Grounding**: Injects DLP findings, proposed domains, and trust levels into the system prompt.
- **Strict Schema Enforcement**: Uses Pydantic models to force the model to return valid JSON matching our internal schemas.

## Components

### `GeminiService`
Located in `pipelines/enterprise_knowledge_base/document_classification/gemini_service.py`.

#### Methods:
- `classify_document(gcs_uri, mime_type, proposed_tier, proposed_domain, trust_level)`:
    - Orchestrates the call to Vertex AI.
    - Validates the response against `ContextualClassificationResponse`.

### `ContextualClassificationResponse` (Schema)
Located in `pipelines/enterprise_knowledge_base/document_classification/schemas.py`.

Fields:
- `final_classification_tier` (int): 1-5.
- `confidence` (float): 0.0 - 1.0.
- `final_domain` (str): Validated business domain.
- `file_description` (str): Summary (< 150 words).

## Security & Authentication
- **IAM-based Authentication**: Uses Application Default Credentials (ADC) for the service account.
- **No Residuals**: Operates on masked documents if sensitive data was found in Phase 1.

## Usage Example
```python
pipeline = ClassificationPipeline()
verdict = pipeline.contextual_classification(
    sanitized_url="gs://bucket/doc_masked.pdf",
    proposed_classification_tier=5,
    proposed_domain="hr",
    trust_level="wip"
)
print(verdict.final_classification_tier) # e.g., 5
```
