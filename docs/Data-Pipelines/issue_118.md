**Issue Title**: Implement vectorization of document chunks

As a developer,
I want to implement an embedding generation method within the RAGIngestion class that vectorizes the chunks in bigquery table `knowledge_base.documents_chunks`,
So that staged chunks are enriched with document metadata and converted into searchable vectors natively inside the data warehouse. The vectorized datra will be used in the RAG Agent to retrieve relevant information using semantic searches.

Acceptance Criteria

Code Complexity Constraint: No function or method may exceed 60 lines of code.
Method Implementation (Vectorization): Implement generate_embeddings(self, gcs_uri).
The method compiles and executes a BigQuery SQL UPDATE statement.
The SQL Logic MUST: 1. Target the knowledge_base.documents_chunks table where gcs_uri matches the input AND embedding IS NULL.
2. JOIN with knowledge_base.documents_metadata on gcs_uri to concatenate or contextualize the text before embedding (e.g., prepending the document description or domain to the chunk_data for a richer vector).
3. Generate the vectorized data using a quick, effective and cost-effective text embedding model from vertex ai.
4. insert/Overwrite the empty embedding column with the resulting vectorized data for the chunks for a specific document UUID.

Output: The method executes the job and returns a boolean True on success, or raises an exception on failure.
Pipeline Orchestration: Update the master orchestrator to call generate_embeddings(gcs_uri) immediately after run_staging(gcs_uri) successfully returns a chunk count > 0.

**Definition of Done**

The method successfully executes a vectorization.
The SQL logic successfully joins the metadata table and updates the target chunk rows.
Integration tests verify that after a pipeline run, the embedding column in documents_chunks is populated with a valid vector array, and no data was pulled out of BigQuery to do it.