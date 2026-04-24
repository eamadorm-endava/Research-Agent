# Module: RAG Ingestion Pipeline

## Overview
The `RAGIngestion` class is responsible for the final stage of the Enterprise Knowledge Base ingestion process. It takes documents that have been successfully classified and routed to their domain buckets, parses them, and chunks their text in alignment with the target embedding model's token limits. These chunks are then staged in BigQuery (`knowledge_base.documents_chunks`) awaiting vectorization via BQML.

## Key Features
- **Deduplication Validation**: Uses `uuid5` on the document's `gcs_uri` to generate a 100% deterministic `document_id`. Queries BigQuery to ensure the document hasn't already been ingested to prevent duplicating chunks, throwing a `FileExistsError` if a match is found.
- **Deterministic Chunking**: Utilizes `RecursiveCharacterTextSplitter` from `langchain-text-splitters` configured to 1000 tokens per chunk to strictly align with LLM embedding limits.
- **PDF Parsing**: Implements `PyMuPDF` (fitz) to accurately extract text and structural layout (including page numbers).
- **Streaming Insertion**: Uses the BigQuery `insert_rows_json` API for high-speed, programmatic streaming of text chunks to the database.

## Components

### `RAGIngestion`
Located in `pipelines/enterprise_knowledge_base/rag_ingestion/rag_ingestion.py`.

#### Methods:
- `process_document(gcs_uri)`: Downloads a document from GCS, parses its contents page-by-page, and returns a structural list of dictionaries adhering to the strict `documents_chunks` schema.
- `run_staging(gcs_uri)`: Orchestrates the pipeline and returns the count of successful chunks processed.

## Architecture Alignment (Vectorization Phase)
This module aligns with the "Vectorization (RAG)" phase defined in `Design.md`.
Instead of generating the embeddings in-memory during this pipeline, it purposefully leaves the `embedding` array empty (`[]`) and `vectorized_at` as `None`. This delegates the actual heavy compute vectorization to BigQuery ML (`BQML`), satisfying the exact architectural design for latency and cost optimization.

## Usage Example
```python
from pipelines.enterprise_knowledge_base.rag_ingestion import RAGIngestion

# Initialize the pipeline
ingestion = RAGIngestion(project_id="ag-core-dev-fdx7")

# Process and stage a document
chunk_count = ingestion.run_staging("gs://kb-it/client-confidential/project-alpha/architecture.pdf")

print(f"Successfully chunked and staged {chunk_count} segments to BigQuery.")
```
