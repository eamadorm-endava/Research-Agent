# RAG Pipeline Deployment

This document describes the automated provisioning and deployment architecture for the Enterprise Knowledge Base RAG Ingestion Pipeline (Issue 117).

## Architecture Overview

The pipeline is wrapped inside a **Cloud Function v2** (backed by Cloud Run) which exposes an HTTP endpoint. It acts as the orchestrator to:
1. Trigger Document Classification (DLP and Gemini contextual masking).
2. Execute RAG Ingestion (PyMuPDF chunking and BigQuery staging).
3. Trigger BigQuery ML multimodal vectorization.

## Infrastructure (Terraform)

All infrastructure is codified in `terraform/rag_ingestion_resources` using Cloud Foundation Fabric modules.

### Provisioned Resources
- **Service Account**: `rag-ingestion-sa`
- **Cloud Function**: `rag-ingestion-function` (Python 3.12 runtime)
- **BigQuery Connection**: `vertex_ext_connection` (Cloud Resource connection for Vertex AI)

### IAM Roles & Least Privilege
The Cloud Function runs as `rag-ingestion-sa`, which is strictly granted the following roles:
- `roles/storage.objectViewer`: To read uploaded PDFs from GCS.
- `roles/bigquery.dataEditor`: To write chunks and update embeddings in BigQuery.
- `roles/aiplatform.user`: To invoke Gemini models during classification.
- `roles/bigquery.connectionUser`: To utilize the Vertex AI connection during BQML queries.

*Note: The function is NOT publicly accessible. Invokers must be authenticated and authorized via IAM (`roles/run.invoker`).*

## CI/CD Pipeline

The deployment is fully automated using Google Cloud Build.
- **Triggers**: Managed via `terraform/scripts/cicd_triggers_creation.sh`.
- **Config**: `pipelines/enterprise_knowledge_base/rag_ingestion/cloudbuild.yaml`
- **Steps**:
  1. Unit testing via `pytest`.
  2. Linting via `pylint` to enforce the 60-statements-per-method architectural constraint.
  3. Infrastructure deployment via `terraform apply`.
  4. Cloud Function deployment is natively handled by Terraform during step 3.

## Invocation

To trigger the pipeline, send an authenticated HTTP POST request to the Cloud Function endpoint:

```bash
# Obtain Identity Token
TOKEN=$(gcloud auth print-identity-token)

# Cloud Function URI (Outputted by Terraform)
FUNCTION_URL="https://rag-ingestion-function-xxx.run.app"

# Send Request
curl -X POST $FUNCTION_URL \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"gcs_uri": "gs://your-bucket-name/ingested/document.pdf"}'
```
