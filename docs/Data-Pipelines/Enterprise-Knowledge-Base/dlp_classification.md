# Module: DLP Classification & Redaction (Phase 1)

## Overview
The `DLPService` acts as the deterministic security gate for the Document Classification Pipeline. It performs high-speed scanning of documents using **Google Cloud DLP** to detect sensitive InfoTypes (PII, Credentials, etc.) and enforces immediate data protection through masking.

## Key Features
- **Deterministic Scanning**: Uses Cloud DLP `inspect` templates to identify hard risks with high precision.
- **Dynamic Masking**: 
    - **Text Documents**: Direct string-based redaction via DLP.
    - **PDF Documents**: Implements a **Split-Redact-Merge** pattern using PyMuPDF and the DLP Image API to ensure visual redaction of embedded sensitive data.
- **Risk Tiering**: Automatically maps findings to Enterprise Knowledge Base (EKB) Tiers 4 and 5 based on pre-defined InfoType severity.

## Components

### `DLPService`
Located in `pipelines/enterprise_knowledge_base/document_classification/dlp_service.py`.

#### Methods:
- `inspect_gcs_file(gcs_uri)`: Starts a DLP inspection job for a specific GCS object.
- `mask_content(content, mime_type, requires_context)`: Redacts sensitive text strings from raw buffers.
- `mask_image_content(image_bytes, mime_type, requires_context)`: Redacts sensitive information from image-based content (used for PDF pages).

### `ClassificationPipeline` Integration
Located in `pipelines/enterprise_knowledge_base/document_classification/pipeline.py`.

#### `dlp_trigger(landing_zone_original_uri)`:
The entry point for Phase 1.
1. Triggers inspection.
2. Maps findings to Tiers 4/5.
3. If risk is detected, creates a `_masked` copy in the same GCS bucket.
4. Returns a `DLPTriggerResponse` containing the sanitized URI.

## Security & Strategy
- **Mask-First, Protect-Always**: Original documents containing sensitive data are never passed to downstream Phase 2 (LLM) services. Only masked versions are processed by Gemini for Tiers 4 and 5.
- **Contextual Masking**: Different masking profiles are applied depending on whether the document requires domain-specific contextual reasoning.

## Usage Example
```python
pipeline = ClassificationPipeline()
response = pipeline.dlp_trigger("gs://landing_zone/payroll_report.pdf")

if response.proposed_classification_tier >= 4:
    print(f"Sensitive document detected. Processing masked version: {response.sanitized_gcs_uri}")
```
