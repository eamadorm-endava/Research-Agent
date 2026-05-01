# BigQuery MCP - Semantic Search Tool

The `ekb_semantic_search` tool provides advanced Retrieval-Augmented Generation (RAG) capabilities by performing vector-based searches against the Enterprise Knowledge Base.

## Overview

Unlike standard SQL queries that rely on keyword matching, semantic search uses machine learning embeddings to find document chunks that are conceptually related to the user's query.

### Key Features
- **Semantic Retrieval**: Uses BQML `VECTOR_SEARCH` with the `multimodal_embedding_model`.
- **Global Search**: Accesses all documents in the knowledge base, including those uploaded by different users.
- **Metadata Filtering**: Supports optional filters for `filename`, `project_id`, `domain`, and `trust_level`.
- **Ranked Results**: Returns chunks ordered by cosine similarity (distance).

## Tool Definition

### `ekb_semantic_search`

**Arguments:**

| Name | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `project_id` | `Enum` | The GCP project where the knowledge base resides. | Required |
| `query` | `string` | The natural language question or topic to search for. | Required |
| `top_k` | `integer` | The number of results to return. | 10 |
| `filename` | `string` | Optional. Filter results by a specific file. | null |
| `project_filter` | `string` | Optional. Filter results by a specific project metadata. | null |
| `domain` | `string` | Optional. Filter results by a business domain (e.g., 'it', 'hr'). | null |
| `trust_level` | `string` | Optional. Filter results by trust maturity (e.g., 'published'). | null |

**Returns:**
A `SemanticSearchResponse` containing a list of `results`, each including:
- `chunk_data`: The text content of the chunk.
- `filename`: The source filename.
- `page_number`: The page where the chunk was found.
- `structural_metadata`: JSON containing layout/structural info.
- `distance`: The semantic distance score (lower is more relevant).
- All metadata fields (`classification_tier`, `domain`, `trust_level`, `project_id`, `uploader_email`).

## Implementation Details

The tool executes a complex BigQuery SQL statement that:
1. Generates a query embedding using `ML.GENERATE_EMBEDDING`.
2. Performs a `VECTOR_SEARCH` against the `knowledge_base.documents_chunks` table.
3. Joins the results with `knowledge_base.documents_metadata` to retrieve rich context and apply filters.
4. Enforces the `m.latest = TRUE` constraint to ensure only the most recent document versions are searched.

## Example Usage

```json
{
  "project_id": "ag-core-dev-fdx7",
  "query": "How do I configure the GCS landing zone?",
  "top_k": 5,
  "domain": "it"
}
```

## Verification

Developers can verify the tool's behavior using the provided notebook:
[semantic_search_verification.ipynb](../../notebooks/big_query/semantic_search_verification.ipynb)
