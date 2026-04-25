import json
import time
import uuid
from datetime import datetime, timezone

import fitz  # PyMuPDF
from google.cloud import bigquery, storage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from .config import RAG_CONFIG
from .schemas import (
    DocumentChunk,
    GenerateEmbeddingsRequest,
    GenerateEmbeddingsResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
)


class RAGIngestion:
    """Parses documents into structural chunks and stages them in BigQuery.

    This service handles the end-to-end flow of document ingestion for RAG,
    including PDF parsing, chunking, BigQuery staging, and vectorization.
    """

    def __init__(self) -> None:
        """Initializes the RAG Ingestion with GCP clients and configuration.

        Returns:
            None -> No return value.
        """
        self.storage_client = storage.Client(project=RAG_CONFIG.PROJECT_ID)
        self.bq_client = bigquery.Client(project=RAG_CONFIG.PROJECT_ID)
        self.table_id = f"{RAG_CONFIG.PROJECT_ID}.{RAG_CONFIG.BQ_DATASET}.{RAG_CONFIG.BQ_CHUNKS_TABLE}"
        logger.info(
            f"Initialized RAGIngestion | CHUNK_SIZE: {RAG_CONFIG.CHUNK_SIZE} | OVERLAP: {RAG_CONFIG.CHUNK_OVERLAP}"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=RAG_CONFIG.CHUNK_SIZE,
            chunk_overlap=RAG_CONFIG.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            is_separator_regex=False,
        )

    def run(self, request: IngestDocumentRequest) -> IngestDocumentResponse:
        """Executes the end-to-end RAG ingestion and vectorization pipeline.

        Args:
            request: IngestDocumentRequest -> The request containing the GCS URI.

        Returns:
            IngestDocumentResponse -> Final result of the end-to-end process.
        """
        logger.info(f"Starting end-to-end pipeline for: {request.gcs_uri}")

        # 1. Ingest document (parse, chunk, stage)
        ingest_resp = self.ingest_document(request)

        # 2. Vectorize if chunks were found
        if ingest_resp.chunk_count > 0:
            embed_req = GenerateEmbeddingsRequest(
                gcs_uri=ingest_resp.processed_uri,
                expected_chunk_count=ingest_resp.chunk_count,
            )
            embed_resp = self.generate_embeddings(embed_req)

            if not embed_resp.success:
                logger.error(f"Vectorization failed: {embed_resp.execution_status}")
                ingest_resp.execution_status = (
                    f"INGESTED_BUT_VECTORIZATION_FAILED: {embed_resp.execution_status}"
                )

        return ingest_resp

    def ingest_document(self, request: IngestDocumentRequest) -> IngestDocumentResponse:
        """Orchestrates the parsing, chunking, staging, and GCS lifecycle.

        Args:
            request: IngestDocumentRequest -> The request containing the GCS URI.

        Returns:
            IngestDocumentResponse -> Summary of the ingestion results.
        """
        logger.info(f"Starting ingestion for document: {request.gcs_uri}")
        # Determine the URI to record in BQ (Original vs Sanitized)
        record_uri = request.original_uri or request.gcs_uri
        execution_id = str(uuid.uuid4())[:8]

        try:
            # 1. Idempotency: Clear existing chunks for this URI to prevent contamination
            self._clear_existing_chunks(record_uri)

            # 2. Staging Copy (Domain -> RAG Staging with Unique Path)
            filename = request.gcs_uri.split("/")[-1]
            staging_path = f"{RAG_CONFIG.GCS_INGESTED_PREFIX}{execution_id}/{filename}"
            staging_uri = f"gs://{RAG_CONFIG.RAG_STAGING_BUCKET}/{staging_path}"

            self._copy_to_staging(request.gcs_uri, staging_uri)

            # 2. Parse and chunk (Read from staging, record Domain URI)
            chunks = self._process_document(read_uri=staging_uri, record_uri=record_uri)
            chunk_count = len(chunks)

            # 3. Stage to BigQuery
            if chunk_count > 0:
                self._stage_chunks_bq(chunks)
                logger.info(f"Successfully staged {chunk_count} chunks to BigQuery.")

            # 4. Lifecycle (Move within Staging Bucket)
            self._move_blob_to_processed(staging_uri)

            return IngestDocumentResponse(
                chunk_count=chunk_count,
                processed_uri=record_uri,  # Report the Domain URI as the primary ref
                execution_status="SUCCESS",
            )

        except FileExistsError as e:
            logger.warning(str(e))
            return IngestDocumentResponse(
                chunk_count=0,
                processed_uri=request.gcs_uri,
                execution_status="SKIPPED_ALREADY_PROCESSED",
            )
        except Exception as e:
            logger.error(f"Ingestion failed for {request.gcs_uri}: {str(e)}")
            raise e

    def generate_embeddings(
        self, request: GenerateEmbeddingsRequest
    ) -> GenerateEmbeddingsResponse:
        """Triggers the BQML vectorization job for a specific document.

        Args:
            request: GenerateEmbeddingsRequest -> The request containing the GCS URI.

        Returns:
            GenerateEmbeddingsResponse -> Result of the vectorization job.
        """
        logger.info(f"Triggering embedding generation for: {request.gcs_uri}")

        model_id = self.table_id.replace(
            RAG_CONFIG.BQ_CHUNKS_TABLE, "multimodal_embedding_model"
        )

        query = f"""
            UPDATE `{self.table_id}` AS target
            SET 
              target.embedding = source.ml_generate_embedding_result,
              target.vectorized_at = CURRENT_TIMESTAMP()
            FROM (
              SELECT * FROM ML.GENERATE_EMBEDDING(
                MODEL `{model_id}`,
                (
                  SELECT c.chunk_id, c.chunk_data AS content
                  FROM `{self.table_id}` c
                  WHERE NORMALIZE(c.gcs_uri) = NORMALIZE(@gcs_uri)
                )
              )
              WHERE ml_generate_embedding_status = ''
            ) AS source
            WHERE target.chunk_id = source.chunk_id;
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("gcs_uri", "STRING", request.gcs_uri)
            ]
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                job = self.bq_client.query(query, job_config=job_config)
                job.result()
                affected_rows = job.num_dml_affected_rows

                # Validation: Did we vectorize what we expected?
                if request.expected_chunk_count > 0:
                    if affected_rows >= request.expected_chunk_count:
                        logger.info(
                            f"Successfully generated embeddings for ALL chunks: {request.gcs_uri}. "
                            f"Rows affected: {affected_rows} (Attempt {attempt + 1})"
                        )
                        return GenerateEmbeddingsResponse(
                            success=True,
                            execution_status=f"SUCCESS: {affected_rows} rows vectorized",
                        )
                    else:
                        logger.warning(
                            f"Partial vectorization on attempt {attempt + 1}: "
                            f"Got {affected_rows}/{request.expected_chunk_count}. Retrying..."
                        )
                elif affected_rows > 0:
                    logger.info(
                        f"Successfully generated embeddings (Attempt {attempt + 1}). "
                        f"Rows affected: {affected_rows}"
                    )
                    return GenerateEmbeddingsResponse(
                        success=True,
                        execution_status=f"SUCCESS: {affected_rows} rows vectorized",
                    )

                logger.warning(
                    f"No rows affected on attempt {attempt + 1}. Retrying in 5s..."
                )
                time.sleep(5)
            except Exception as e:
                logger.error(
                    f"Embedding generation attempt {attempt + 1} failed: {str(e)}"
                )
                if attempt == max_retries - 1:
                    return GenerateEmbeddingsResponse(
                        success=False, execution_status=str(e)
                    )
                time.sleep(5)

        return GenerateEmbeddingsResponse(
            success=False,
            execution_status="FAILED: No rows were vectorized after retries.",
        )

    def _clear_existing_chunks(self, gcs_uri: str) -> None:
        """Deletes all chunks associated with a specific GCS URI.

        Args:
            gcs_uri: str -> The URI to clear from the chunks table.

        Returns:
            None -> No return value.
        """
        query = f"DELETE FROM `{self.table_id}` WHERE NORMALIZE(gcs_uri) = NORMALIZE(@gcs_uri)"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("gcs_uri", "STRING", gcs_uri)
            ]
        )
        try:
            job = self.bq_client.query(query, job_config=job_config)
            job.result()
            logger.info(
                f"Cleared {job.num_dml_affected_rows} existing chunks for: {gcs_uri}"
            )
        except Exception as e:
            logger.warning(f"Failed to clear existing chunks: {str(e)}")

    def _process_document(self, read_uri: str, record_uri: str) -> list[DocumentChunk]:
        """Downloads, parses, and chunks a document into BQ-compatible objects.

        Args:
            read_uri: str -> The URI to read the file from (Staging).
            record_uri: str -> The URI to record in BigQuery (Domain).

        Returns:
            list[DocumentChunk] -> List of validated chunk objects.
        """
        document_id = self._generate_document_id(record_uri)

        if self._is_document_processed(document_id):
            raise FileExistsError(f"Document {record_uri} has already been processed.")

        bucket_name = read_uri.replace("gs://", "").split("/")[0]
        blob_name = read_uri.replace(f"gs://{bucket_name}/", "")
        filename = blob_name.split("/")[-1]

        blob = self.storage_client.bucket(bucket_name).blob(blob_name)
        file_bytes = blob.download_as_bytes()

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        chunks_list = []

        try:
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                if not text.strip():
                    continue

                for chunk_text in self.text_splitter.split_text(text):
                    chunk = DocumentChunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id=document_id,
                        chunk_data=chunk_text,
                        gcs_uri=record_uri,
                        filename=filename,
                        structural_metadata=json.dumps(
                            {"title": filename, "page": page_num}
                        ),
                        page_number=page_num,
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                    chunks_list.append(chunk)
        finally:
            doc.close()

        return chunks_list

    def _stage_chunks_bq(self, chunks: list[DocumentChunk]) -> None:
        """Batch loads chunks into BigQuery to bypass streaming buffer.

        Args:
            chunks: list[DocumentChunk] -> List of chunks to persist.

        Returns:
            None -> No return value.
        """
        if not chunks:
            return

        json_rows = [chunk.model_dump() for chunk in chunks]
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )

        try:
            job = self.bq_client.load_table_from_json(
                json_rows, self.table_id, job_config=job_config
            )
            job.result()
        except Exception as e:
            raise RuntimeError(f"BigQuery batch load failed: {str(e)}")

    def _copy_to_staging(self, source_uri: str, destination_uri: str) -> None:
        """Copies a document from its source (Domain) to the RAG Staging bucket.

        Args:
            source_uri: str -> Source Domain URI.
            destination_uri: str -> Destination Staging URI.

        Returns:
            None
        """
        logger.info(f"Staging document: {source_uri} -> {destination_uri}")
        src_bucket_name = source_uri.replace("gs://", "").split("/")[0]
        src_blob_name = source_uri.replace(f"gs://{src_bucket_name}/", "")
        dst_bucket_name = destination_uri.replace("gs://", "").split("/")[0]
        dst_blob_name = destination_uri.replace(f"gs://{dst_bucket_name}/", "")

        src_bucket = self.storage_client.bucket(src_bucket_name)
        dst_bucket = self.storage_client.bucket(dst_bucket_name)
        src_blob = src_bucket.blob(src_blob_name)

        src_bucket.copy_blob(src_blob, dst_bucket, dst_blob_name)

    def _move_blob_to_processed(self, staging_uri: str) -> str:
        """Moves a document from staging ingestion to staging processed storage.

        Args:
            staging_uri: str -> The staging GCS URI.

        Returns:
            str -> The new staging GCS URI.
        """
        bucket_name = staging_uri.replace("gs://", "").split("/")[0]
        blob_name = staging_uri.replace(f"gs://{bucket_name}/", "")

        if RAG_CONFIG.GCS_INGESTED_PREFIX not in blob_name:
            logger.debug(f"Blob {blob_name} not in ingested prefix, skipping move.")
            return staging_uri

        new_blob_name = blob_name.replace(
            RAG_CONFIG.GCS_INGESTED_PREFIX, RAG_CONFIG.GCS_PROCESSED_PREFIX, 1
        )
        bucket = self.storage_client.bucket(bucket_name)
        source_blob = bucket.blob(blob_name)

        logger.debug(f"Moving staging file {blob_name} to {new_blob_name}")
        bucket.copy_blob(source_blob, bucket, new_blob_name)
        source_blob.delete()

        return f"gs://{bucket_name}/{new_blob_name}"

    def _generate_document_id(self, gcs_uri: str) -> str:
        """Generates a deterministic UUID based on the GCS URI.

        Args:
            gcs_uri: str -> The GCS URI of the document.

        Returns:
            str -> The generated UUID string.
        """
        return str(uuid.uuid5(uuid.NAMESPACE_URL, gcs_uri))

    def _is_document_processed(self, document_id: str) -> bool:
        """Checks if the document ID already exists in the chunks table.

        Args:
            document_id: str -> The UUID of the document to check.

        Returns:
            bool -> True if the document has already been processed.
        """
        query = f"SELECT 1 FROM `{self.table_id}` WHERE document_id = @doc_id LIMIT 1"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("doc_id", "STRING", document_id)
            ]
        )
        query_job = self.bq_client.query(query, job_config=job_config)
        return len(list(query_job.result())) > 0
