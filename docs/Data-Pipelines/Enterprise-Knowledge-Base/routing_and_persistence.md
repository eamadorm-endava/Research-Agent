# Document Classification Pipeline: Routing and Persistence (Step 03)

This module handles the physical relocation of documents to their target domain buckets and the registration of their metadata in BigQuery.

## GCS Routing Logic

The routing logic is authoritative and follows the classification verdict produced by Phase 2 (Gemini).

### Destination Path Construction
The target URI is constructed as follows:
`gs://kb-{domain}/{project_name}/{tier_label}/{uploader_email_prefix}/{filename}`

- **domain**: One of the valid business domains (`it`, `finance`, `hr`, etc.).
- **tier_label**: The slugified version of the security tier (e.g., `strictly-confidential` for Tier 5).
- **project_name**: The project identifier provided during ingestion.
- **uploader_email_prefix**: The local part of the uploader's email address.

### Dual-File Routing
Per security requirements, if a masked version of the document was generated during Phase 1 (DLP), **both** the original and the masked files are moved to the domain bucket.

### Landing Zone Cleanup
The landing zone is cleaned up only after successful verification of the move. No original or masked files are allowed to remain in the landing zone bucket after processing.

---

## BigQuery Metadata Schema

Metadata is stored in the `knowledge_base` dataset, `documents_metadata` table.

| Field | Type | Description |
|---|---|---|
| `document_id` | `STRING` | Unique UUID for the document record. |
| `gcs_uri` | `STRING` | The URI of the original document in the domain bucket (used for search/RAG). |
| `filename` | `STRING` | Original filename. |
| `classification_tier` | `INT64` | Numeric classification tier (1-5). |
| `domain` | `STRING` | Valid business domain. |
| `confidence_score` | `FLOAT64` | AI confidence score (0.0 - 1.0). |
| `trust_level` | `STRING` | Trust maturity (published, wip, archived). |
| `project_id` | `STRING` | Project identifier. |
| `uploader_email` | `STRING` | Email of the uploader. |
| `description` | `STRING` | AI-generated summary of the content. |
| `version` | `INT64` | Incremental version number. |
| `is_latest` | `BOOL` | Flag for the latest version. |
| `ingested_at` | `TIMESTAMP` | Timestamp of ingestion (UTC). |

---

## Technical Services

The implementation follows a modular service pattern located in `pipelines/enterprise_knowledge_base/document_classification/`:

### gcs_service
Handles cross-bucket relocation and metadata extraction.
- **Import**: `from .gcs_service.service import GCSService`

### bq_service
Dedicated service for BigQuery streaming inserts, ensuring atomicity and auditability.
- **Import**: `from .bq_service.service import BQService`

### Best Practices
- **Relative Imports**: All internal service communication uses relative imports (e.g., `from ..config import ...`).
- **Validation**: All service interfaces are validated using Pydantic models defined in each service's `schemas.py`.
