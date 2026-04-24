As a developer,
I want to implement a Python-based RAGIngestion class that parses documents into structural chunks and stages them in BigQuery,
So that unstructured documents are broken down into precise, model-aligned text segments with a placeholder for future vectorization.

Acceptance Criteria

Code Complexity Constraint: No function or method may exceed 60 lines of code.

Method Implementation 1 (Extraction & Chunking): Implement process_document(self, gcs_uri).

Downloads the file, parses it (e.g., to Markdown), and extracts structural hierarchy and page numbers.
Applies a chunking strategy where the chunk size is strictly aligned with the target embedding model's token limits.
Returns a list of dictionaries. Each dictionary MUST contain these exact keys:
chunk_id (STRING/UUID)
chunk_data (STRING)
gcs_uri (STRING)
filename (STRING)
structural_metadata (JSON/Dict - e.g., {"title": "...", "subtitle": "..."})
page_number (INT)
embedding (Set to NULL or an empty array initially)
created_at (TIMESTAMP - UTC)
vectorized_at (TIMESTAMP - UTC - set to NULL as embedding still not generated)
Method Implementation 2 (Persistence): Implement stage_chunks_bq(self, chunks_list).

Performs a streaming insert or batch load of the dictionary list into the BigQuery table knowledge_base.documents_chunks.
Method Implementation 3 (Orchestrator): Implement a public run_staging(self, gcs_uri) method that executes the above and returns the integer count of how many chunks were successfully stored.

Definition of Done

The RAGIngestion class methods are fully implemented and adhere to the 60-line rule.
Unit tests verify that the output dictionary perfectly matches the required keys and that token limits are respected.
Integration tests confirm chunks are successfully inserted into knowledge_base.documents_chunks with a NULL/empty embedding field, and the method returns the correct chunk count.