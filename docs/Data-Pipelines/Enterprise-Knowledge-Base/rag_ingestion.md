# RAG Ingestion Module

This module handles the automated ingestion of documents into the Enterprise Knowledge Base (EKB).

## Core Responsibilities
- **Parsing**: Extracts text from PDFs using `PyMuPDF` (fitz).
- **Chunking**: Splits text into semantic chunks using `RecursiveCharacterTextSplitter`.
- **Staging**: Loads chunks into BigQuery using Load Jobs.
- **Vectorization**: Generates embeddings using BigQuery ML (`multimodalembedding`).

## Technical Configuration
The module is configured via `RAGConfig` in `pipelines/enterprise_knowledge_base/rag_ingestion/config.py`.

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `CHUNK_SIZE` | 1000 | Max characters per chunk (Model limit: 1024). |
| `CHUNK_OVERLAP` | 150 | Overlapping characters between chunks (15%). |
| `BQ_DATASET` | `knowledge_base` | Target BigQuery dataset. |
| `BQ_CHUNKS_TABLE` | `documents_chunks` | Table for storing vectorized chunks. |

## Process Flow
1. **Idempotency Check**: Clears existing chunks for the target URI before processing.
2. **Parsing**: Extracts raw text page-by-page from the source PDF.
3. **Recursive Chunking**: Applies hierarchical splitting (`\n\n`, `\n`, `. `, ` `) to maintain context.
4. **BQ Staging**: Uses `load_table_from_json` to bypass the streaming buffer and ensure immediate DML availability.
5. **ML Vectorization**: Triggers `ML.GENERATE_EMBEDDING` via an `UPDATE` query on the loaded rows.

## Best Practices & Lessons Learned

### 1. The 1,024 Character Limit
The `multimodalembedding` model has a strict **1,024 character limit** for the input text. 
> [!IMPORTANT]
> Always use a "Pure Content" strategy. Do not inject metadata (like Domain or Description) into the embedding input field, as this often pushes the total length over the limit and causes vectorization failures.

### 2. Streaming Buffer Conflicts
Standard BigQuery insertions (`insert_rows_json`) place data in a streaming buffer that is **read-only** for DML updates (like `UPDATE ... SET embedding = ...`) for up to 90 minutes.
> [!TIP]
> Always use `load_table_from_json` (Load Jobs). This writes directly to managed storage, making the rows immediately available for vectorization.

### 3. URI Normalization & Deterministic IDs
Use `NORMALIZE(gcs_uri)` in all BigQuery SQL queries to handle hidden spaces or different Unicode representations of file paths. The pipeline relies on a deterministic UUIDv5 generated from the NFC-normalized GCS URI to ensure `document_id` consistency between the `documents_metadata` and `documents_chunks` tables.

## Troubleshooting
- **0 affected rows in UPDATE**: Check if the data is stuck in the streaming buffer (if Load Jobs were not used).
- **INVALID_ARGUMENT (1024 chars)**: Verify that `chunk_data` is strictly under the limit and that no prefixes are being added in the SQL query.
