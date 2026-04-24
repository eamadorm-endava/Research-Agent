import json
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
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=RAG_CONFIG.CHUNK_SIZE,
            chunk_overlap=RAG_CONFIG.CHUNK_OVERLAP,
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
            embed_req = GenerateEmbeddingsRequest(gcs_uri=ingest_resp.processed_uri)
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

        try:
            # 1. Parse and chunk
            chunks = self._process_document(request.gcs_uri)
            chunk_count = len(chunks)

            # 2. Stage to BigQuery
            if chunk_count > 0:
                self._stage_chunks_bq(chunks)
                logger.info(f"Successfully staged {chunk_count} chunks to BigQuery.")

            # 3. Move to processed prefix
            processed_uri = self._move_blob_to_processed(request.gcs_uri)

            return IngestDocumentResponse(
                chunk_count=chunk_count,
                processed_uri=processed_uri,
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
        metadata_id = self.table_id.replace(
            RAG_CONFIG.BQ_CHUNKS_TABLE, RAG_CONFIG.BQ_METADATA_TABLE
        )

        query = f"""
            UPDATE `{self.table_id}` AS target
            SET embedding = source.ml_generate_embedding_result
            FROM (
              SELECT * FROM ML.GENERATE_EMBEDDING(
                MODEL `{model_id}`,
                (
                  SELECT c.chunk_id, CONCAT(
                    'Domain: ', IFNULL(m.domain, 'Unknown'), '\\n',
                    'Description: ', IFNULL(m.description, 'None'), '\\n',
                    'Content: ', IFNULL(c.chunk_data, '')
                  ) AS content
                  FROM `{self.table_id}` c
                  LEFT JOIN `{metadata_id}` m ON c.gcs_uri = m.gcs_uri
                  WHERE c.gcs_uri = @gcs_uri AND (c.embedding IS NULL OR ARRAY_LENGTH(c.embedding) = 0)
                )
              )
            ) AS source
            WHERE target.chunk_id = source.chunk_id;
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("gcs_uri", "STRING", request.gcs_uri)
            ]
        )

        try:
            self.bq_client.query(query, job_config=job_config).result()
            logger.info(f"Successfully generated embeddings for: {request.gcs_uri}")
            return GenerateEmbeddingsResponse(success=True, execution_status="SUCCESS")
        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            return GenerateEmbeddingsResponse(success=False, execution_status=str(e))

    def _process_document(self, gcs_uri: str) -> list[DocumentChunk]:
        """Internal helper to download and parse a PDF into chunks.

        Args:
            gcs_uri: str -> The GCS URI of the document.

        Returns:
            list[DocumentChunk] -> List of validated chunk objects.
        """
        document_id = self._generate_document_id(gcs_uri)

        if self._is_document_processed(document_id):
            raise FileExistsError(f"Document {gcs_uri} has already been processed.")

        bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
        blob_name = gcs_uri.replace(f"gs://{bucket_name}/", "")
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
                        gcs_uri=gcs_uri,
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

    def _move_blob_to_processed(self, gcs_uri: str) -> str:
        """Moves a document from ingestion landing to processed storage.

        Args:
            gcs_uri: str -> The original GCS URI.

        Returns:
            str -> The new GCS URI.
        """
        bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
        blob_name = gcs_uri.replace(f"gs://{bucket_name}/", "")

        if RAG_CONFIG.GCS_INGESTED_PREFIX not in blob_name:
            logger.debug(f"Blob {blob_name} not in ingested prefix, skipping move.")
            return gcs_uri

        new_blob_name = blob_name.replace(
            RAG_CONFIG.GCS_INGESTED_PREFIX, RAG_CONFIG.GCS_PROCESSED_PREFIX, 1
        )
        bucket = self.storage_client.bucket(bucket_name)
        source_blob = bucket.blob(blob_name)

        logger.debug(f"Moving {blob_name} to {new_blob_name}")
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
