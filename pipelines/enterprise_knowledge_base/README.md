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
The pipeline requires a Service Account with the following minimum IAM roles:

#### 1. Pipeline Execution SA
Used by the Cloud Run/Function or local orchestrator.
- `roles/dlp.user`: To scan and mask PII.
- `roles/storage.objectAdmin`: To manage files across landing, staging, and domain buckets.
- `roles/bigquery.dataEditor`: To insert records into BQ tables.
- `roles/bigquery.jobUser`: To run BQ Load Jobs and queries.
- `roles/aiplatform.user`: To invoke Gemini for classification.

#### 2. BigQuery Connection SA
Automatically created when provisioning the BigQuery Cloud Resource Connection.
- `roles/aiplatform.user`: **Required** to allow BQML to call Vertex AI embedding models.

### IAM Setup Command
```bash
# Granting Vertex AI access to the BQ Connection SA
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${CONNECTION_SA_EMAIL}" \
  --role="roles/aiplatform.user"
```

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
