# EKB RAG Ingestion & Vectorization Pipeline (Phase 2)

This service implements **Phase 2** of the Enterprise Knowledge Base (EKB) pipeline. It handles the semantic decomposition of documents into searchable units and generates high-dimensional vector embeddings for AI-powered retrieval (RAG).

## 1. Role in the EKB Architecture

As the second stage of the `KBIngestionPipeline`, this component takes the **Original URI** (the unmasked, secured document) and prepares it for semantic search. It transforms static files into a queryable knowledge graph.

### Pipeline Workflow
1. **Idempotency Check**: Cleans up any existing chunks for the document URI to prevent duplicates.
2. **Recursive Chunking**: Hierarchically splits text to maintain semantic context across chunks.
3. **High-Performance Staging**: Uses BigQuery Load Jobs to ensure data is immediately available for vectorization.
4. **Vectorization**: Generates embeddings using the `multimodalembedding` model via BigQuery ML.

---

## 2. High-Performance Design Patterns

To ensure reliability and speed, this pipeline implements several critical design patterns:

### Bypassing the Streaming Buffer
Standard BigQuery streaming (`insert_rows_json`) creates a read-only buffer that blocks DML updates for up to 90 minutes. This pipeline uses **Load Jobs** (`load_table_from_json`), which writes directly to managed storage.
- **Benefit**: Rows are available for the `UPDATE` vectorization query **immediately**.

### Pure Content Vectorization
The `multimodalembedding` model has a strict **1,024 character limit**.
- **Strategy**: We vectorize **only** the raw text chunk (`chunk_data`). Metadata (Domain, Title, Description) is stored in separate columns for filtering but is excluded from the embedding input to prevent length overflows and maximize context window.

### Ghost URI Prevention
To handle subtle encoding or trailing space differences in GCS URIs, all BigQuery operations use `NORMALIZE(gcs_uri)`. This ensures that the ingestion and vectorization steps always target the same binary record.

---

## 3. Configuration

Managed via `RAGConfig` in `config.py`.

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `CHUNK_SIZE` | 1000 | Max characters per chunk (safely under 1024 limit). |
| `CHUNK_OVERLAP` | 150 | Overlapping characters between chunks (15% recommended). |
| `BQ_CHUNKS_TABLE` | `documents_chunks` | Target table for vectorized units. |
| `RAG_STAGING_BUCKET` | `*-rag-staging` | Temporary bucket for file processing. |

---

## 4. Package Structure

```text
rag_ingestion/
├── tests/                  # Regression suite (limits, SQL, staging)
├── config.py               # Component configuration (BaseSettings)
├── pipeline.py             # RAGIngestion orchestrator
├── schemas.py              # Pydantic Request/Response models
└── README.md               # This documentation
```

### Key Logic Components
- **`RecursiveCharacterTextSplitter`**: Configured with separators `["\n\n", "\n", ". ", " ", ""]` to prioritize paragraph and sentence boundaries.
- **`GenerateEmbeddingsRequest`**: Specifically designed to validate and track the expected chunk count before triggering ML jobs.

---

## 5. Operations & Verification

### Running Tests
```bash
uv run pytest pipelines/enterprise_knowledge_base/rag_ingestion/tests/
```

### Verification Query
To check the vectorization status of a document:
```sql
SELECT gcs_uri, count(*) as chunks, countif(array_length(embedding) > 0) as vectorized
FROM `knowledge_base.documents_chunks`
WHERE NORMALIZE(gcs_uri) = NORMALIZE('gs://your-bucket/your-file.pdf')
GROUP BY gcs_uri
```
