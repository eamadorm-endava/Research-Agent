# RAG Ingestion Pipeline

## Overview
The `RAGIngestion` component is the final stage of the Enterprise Knowledge Base (EKB) ingestion process. It is responsible for taking unstructured documents that have been classified and routed, parsing their structural data (like text and page numbers), and splitting them into precise chunks. These chunks are securely staged in BigQuery where they await vectorization by BigQuery ML (BQML), enabling the Gemini Enterprise AI Agent to perform Semantic Search.

## End-to-End Workflow & Architecture

The ingestion and vectorization lifecycle follows a strict sequence to ensure security and compliance before data is ever made searchable:

### 1. Human-in-the-Loop Ingestion (The AI Agent)
The journey begins when a user uploads a document (like a PDF) directly to the **Gemini Enterprise AI Agent** chat interface.
* The Agent triggers the **Ingestion Metadata Skill** to ask the user clarifying questions (Project, Draft/Published status).
* Using the **end-user's delegated OAuth token**, the Agent writes the document to the landing zone bucket (`gs://ag-core-dev-fdx7-kb-landing-zone`) and attaches the answers as custom GCS metadata.

### 2. The Security Gate: Cloud DLP (Phase 1)
The orchestrator triggers the `DLPService`.
* Cloud DLP deterministically scans the document for highly sensitive data (SSNs, APIs, strategic keywords).
* **"Mask-First" Rule:** If flagged as **Tier 4** (Confidential) or **Tier 5** (Strictly Confidential), DLP generates a heavily redacted `_masked` copy in the landing zone.

### 3. Contextual AI Classification (Phase 2)
The orchestrator passes the document to Gemini 2.5 Flash.
* For Tier 4/5, Gemini *only* reads the safe `_masked` version.
* Gemini outputs a structured verdict containing the final **Classification Tier**, the **Business Domain** (e.g., HR, Finance, IT), and an AI-generated summary.

### 4. Routing and Metadata Extraction
The orchestrator physically moves the **original (unmasked)** file into a highly restricted, domain-specific GCS bucket (e.g., `gs://kb-it/Tier-4/`). 
* The temporary `_masked` file is permanently deleted from the landing zone.
* A record of the file's metadata and AI summary is written to the `knowledge_base.documents_metadata` table in BigQuery.

### 5. Extraction & Chunking (This Module)
Once safely stored in its domain bucket, the orchestrator triggers the `RAGIngestion` class.
* **Deduplication Check**: The module generates a highly deterministic UUID hash (using `uuid5`) based on the GCS URI, and queries BigQuery to guarantee the document hasn't been processed before. If it has, the ingestion is instantly aborted.
* The module downloads the file and uses `PyMuPDF` to parse the text page-by-page.
* It passes the text through the `RecursiveCharacterTextSplitter`, which breaks the document down into precise, overlapping **1,000-token chunks** (perfectly aligned with downstream LLM embedding limits).

### 6. BigQuery Staging & BQML Vectorization
The module packages each chunk into a strict dictionary format (capturing the chunk text, source page number, UUID, and GCS URI) and executes a high-speed streaming insert into the `knowledge_base.documents_chunks` BigQuery table. 
* **The Vectorization Handoff:** The module intentionally leaves the `embedding` vector as an empty array (`[]`). The pipeline delegates the actual heavy compute to **BigQuery ML (BQML)**, which natively executes an embedding model against the raw chunk text right inside the database.
* **Lifecycle State Change**: Upon successful insertion into BigQuery, the `RAGIngestion` module will move the physical file from the `ingested/` subdirectory to the `processed/` subdirectory within its bucket, ensuring no duplicate processing.

## Requirements

This module is managed under the `rag_pipeline` dependency group in `pyproject.toml`. It requires the following packages:
- `google-cloud-storage`: For downloading the document bytes from GCS.
- `google-cloud-bigquery`: For performing streaming JSON inserts (`insert_rows_json`) to the `documents_chunks` table.
- `pymupdf` (fitz): For highly accurate PDF text and page extraction.
- `langchain-text-splitters`: Provides the `RecursiveCharacterTextSplitter` to ensure chunks align perfectly with token limits.

## Files

| File | Description |
|---|---|
| `__init__.py` | Exposes the `RAGIngestion` class. |
| `rag_ingestion.py` | Contains the `RAGIngestion` class. Adheres to strict 60-line method limits and handles all parsing, chunking, and BQ insertion logic. |
| `main.py` | Cloud Function HTTP entry point that wraps the `KBIngestionPipeline` orchestrator. |
| `cloudbuild.yaml` | Cloud Build CI/CD configuration to test, lint (enforce 60-statement limit), and deploy via Terraform. |
| `../../tests/test_rag_ingestion.py` | Contains isolated Mock-based Pytest unit and integration tests. |
| `../../../notebooks/enterprise_knowledge_base/rag_ingestion/rag_verification.ipynb` | A Jupyter Notebook for testing the pipeline end-to-end, including Cloud Function HTTP endpoint invocation. |

## Manual Testing via Notebook

To manually test the RAG Ingestion pipeline and verify BigQuery insertions using the provided Stage 1 notebook, follow these steps:

1. **Authenticate**: Ensure you are authenticated with Google Cloud and have Application Default Credentials set:
   ```bash
   gcloud auth application-default login
   gcloud config set project ag-core-dev-fdx7
   ```

2. **Upload a Sample Document**: Upload a test PDF to the newly created landing zone bucket. You can do this via the GCP Console or CLI:
   ```bash
   gsutil cp path/to/local/sample.pdf gs://ag-core-dev-fdx7-kb-landing-zone/sample.pdf
   ```

3. **Open the Notebook**: Launch the notebook environment using the project's dependency manager.
   ```bash
   uv run --group rag_pipeline jupyter notebook notebooks/enterprise_knowledge_base/rag_ingestion/rag_verification.ipynb
   ```
   *(Alternatively, open the `.ipynb` file directly in your IDE like VS Code and select the `uv` virtual environment as your kernel).*

4. **Execute the Pipeline**:
   - In the notebook, locate the `GCS_URI` variable and update it to match your uploaded file: 
     `GCS_URI = "gs://ag-core-dev-fdx7-kb-landing-zone/sample.pdf"`
   - Uncomment the execution lines (`count = ingestion.run_staging(GCS_URI)`) and run the cell. You should see an output indicating how many chunks were staged.

5. **Verify in BigQuery**:
   - Run the final cell in the notebook to query the `knowledge_base.documents_chunks` table. 
   - Verify that the `chunk_data` contains the parsed text, `structural_metadata` contains the page number, and the `embedding` array is empty (`[]`) or populated if vectorization ran.

## Automated Deployment (Cloud Function)

The `RAGIngestion` module is deployed as a fully automated HTTP-triggered **Cloud Function v2** via Terraform. It is wrapped by the `KBIngestionPipeline` orchestrator (`orchestrator.py`), which ensures that Document Classification runs successfully before RAG ingestion begins.

1. **Deployment Architecture**:
   - Deployed using Cloud Foundation Fabric (CFF) Terraform modules in `terraform/rag_ingestion_resources/`.
   - The Cloud Function executes as a dedicated service account (`rag-ingestion-sa`) with least-privilege IAM roles.
   - Triggered securely; unauthenticated invocation is blocked.
2. **CI/CD Pipeline**:
   - Fully automated through Cloud Build (`cloudbuild.yaml`).
   - Triggered on PRs and merges to the `main` branch.
   - Enforces a 60-statements-per-method limit using `pylint`.
