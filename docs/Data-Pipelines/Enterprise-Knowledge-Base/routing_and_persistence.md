# Document Classification Pipeline: Routing and Persistence (Step 03)

This module handles the physical relocation of documents to their target domain buckets and the registration of their metadata in BigQuery.

## GCS Routing Logic

The routing logic is authoritative and follows the classification verdict produced by Phase 2 (Gemini).

### Destination Path Construction
The target URI is constructed as follows:
`gs://kb-{domain}/{tier_label}/{project_name}/{uploader_email_prefix}/{filename}`

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

### GCSService
Enhanced with `copy_blob` and `delete_blob` to handle cross-bucket relocation.

### BQService
Dedicated service for BigQuery streaming inserts, ensuring atomicity and auditability of metadata records.
