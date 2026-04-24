# Document Classification Orchestration

The `ClassificationPipeline.run()` method serves as the central entry point for the Enterprise Knowledge Base document processing workflow. It orchestrates multiple specialized services to transform a raw document into a classified, secured, and versioned asset.

## Workflow Overview

The orchestration follows a strictly sequential flow:

1.  **Metadata Extraction**: Retrieves initial GCS blob properties (filename, project tags, uploader identity).
2.  **DLP Gate**: Scans the document for sensitive data (PII, secrets). If high-risk content is found, it creates a de-identified/masked version.
3.  **Contextual Classification**: Uses Gemini (Vertex AI) to analyze the (possibly masked) document and determine its final security tier and business domain.
4.  **File Routing**: Moves the original and masked files from the landing zone to the final domain-specific buckets based on the classification results.
5.  **Persistence**: Records the final URIs, classification metadata, and versioning state in BigQuery.

## State Management

The pipeline maintains an in-memory state of the document metadata throughout its execution. This ensures that even if files are moved or deleted in GCS, the audit trail in BigQuery remains accurate and complete.

## Error Handling & Cleanup

To ensure system resilience and data consistency:

*   **Atomic-like Execution**: The entire pipeline is wrapped in a high-level exception handler.
*   **Cleanup Protocol**: If a failure occurs after the DLP stage but before routing, the pipeline automatically deletes any intermediate masked files created in the landing zone.
*   **Landing Zone Integrity**: The original document in the landing zone is never deleted if the pipeline fails, allowing for manual investigation and retries.
*   **Logging**: Every failure point is logged with full context to aid in debugging.

## Usage Example

```python
from pipelines.enterprise_knowledge_base import ClassificationPipeline

pipeline = ClassificationPipeline()
result = pipeline.run("gs://landing-zone-bucket/new_upload.pdf")

print(f"Final Domain: {result.final_domain}")
print(f"Security Tier: {result.final_security_tier}")
print(f"Sanitized URI: {result.final_sanitized_uri}") # Returns masked file if exists, else original destination
```
