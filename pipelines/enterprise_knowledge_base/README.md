# Enterprise Knowledge Base (EKB) Ingestion Pipeline

This pipeline automates the secure ingestion, classification, and indexing of corporate documents into a centralized knowledge base for AI-powered retrieval.

## Architecture Overview

The pipeline follows a two-stage orchestrated workflow:
1. **Document Classification**: Scans for PII via DLP, classifies business domain via Gemini, and routes files to secure domain-specific buckets.
2. **RAG Ingestion**: Copies files to an internal staging area, chunks the text, persists to BigQuery, and generates semantic embeddings using Vertex AI.

---

## Infrastructure Requirements

### Google Cloud Services
The following APIs must be enabled:
- `dlp.googleapis.com` (Cloud Data Loss Prevention)
- `storage.googleapis.com` (Cloud Storage)
- `aiplatform.googleapis.com` (Vertex AI)
- `bigquery.googleapis.com` (BigQuery)
- `cloudresourcemanager.googleapis.com` (Resource Management)

### GCS Buckets
| Bucket Purpose | Default Name Pattern |
| :--- | :--- |
| **Landing Zone** | `${PROJECT_ID}-kb-landing-zone` |
| **RAG Staging** | `${PROJECT_ID}-rag-staging` |
| **Domain Storage** | `kb-finance`, `kb-it`, `kb-hr`, etc. |

### BigQuery Dataset: `knowledge_base`
- **`documents_metadata`**: Stores classification, routing, and versioning information.
- **`documents_chunks`**: Stores text chunks and vector embeddings.
- **`multimodal_embedding_model`**: A BQML remote model connected to Vertex AI.

---

## Security & Permissions

### Service Account (SA) Requirements
The pipeline operates on a **least-privilege model**, using resource-level bindings where possible.

#### 1. Pipeline Execution SA (`ekb-pipeline-sa`)
Used by the Cloud Run service or local orchestrator.

**Project Level Roles:**
- `roles/dlp.admin`: To manage inspection jobs.
- `roles/bigquery.jobUser`: To run BQ Load Jobs and queries.
- `roles/aiplatform.user`: To invoke Gemini and Vertex AI.
- `roles/logging.logWriter`: For container logs.

**Resource Level Roles:**
- `roles/storage.objectAdmin`: Granted ONLY on Landing, RAG Staging, and Domain buckets.
- `roles/bigquery.dataEditor`: Granted ONLY on the `knowledge_base` dataset.
- `roles/bigquery.connectionUser`: Granted on the `vertex_ai_connection` to allow BQML queries.

#### 2. BigQuery Connection SA
Automatically created when provisioning the BigQuery Cloud Resource Connection.
- `roles/aiplatform.user`: **Required** at the project level to allow BQML to call Vertex AI embedding models.

---

## Configuration

### Environment Variables
The following variables are required for the Cloud Run deployment (configured via Terraform):

| Variable | Description |
| :--- | :--- |
| `PROJECT_ID` | The GCP Project ID. |
| `GEMINI_LOCATION` | The region for Vertex AI (e.g., `us-central1`). |
| `BQ_DATASET` | Name of the metadata dataset. |
| `BQ_TABLE` | Main metadata table name. |
| `BQ_CHUNKS_TABLE` | Table for storing document chunks. |
| `BQ_METADATA_TABLE` | (Duplicate of BQ_TABLE) for backward compatibility. |
| `RAG_STAGING_BUCKET` | The bucket name for the RAG staging area. |
| `GEMINI_MODEL` | (Optional) Defaults to `gemini-2.5-flash`. |

---

## Operations

### Setup
To provision the entire infrastructure:
```bash
bash pipelines/enterprise_knowledge_base/create_resources.sh <your-project-id>
```

### Teardown
To delete all resources and data:
```bash
bash pipelines/enterprise_knowledge_base/delete_resources.sh <your-project-id>
```

### Local Execution
```bash
uv run --group rag_pipeline --group classification_pipeline python -m pipelines.enterprise_knowledge_base.orchestrator <project_id> <gcs_uri>
```
