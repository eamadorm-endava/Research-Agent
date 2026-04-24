import json
import uuid
from datetime import datetime, timezone
import fitz  # PyMuPDF
from google.cloud import storage, bigquery
from langchain_text_splitters import RecursiveCharacterTextSplitter

class RAGIngestion:
    """Parses documents into structural chunks and stages them in BigQuery."""
    
    def __init__(self, project_id: str, bq_dataset: str = "knowledge_base"):
        self.storage_client = storage.Client(project=project_id)
        self.bq_client = bigquery.Client(project=project_id)
        self.table_id = f"{project_id}.{bq_dataset}.documents_chunks"
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
        )

    def _generate_document_id(self, gcs_uri: str) -> str:
        """Generates a deterministic UUID based on the GCS URI."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, gcs_uri))

    def _is_document_processed(self, document_id: str) -> bool:
        """Checks BigQuery to see if the document has already been ingested."""
        query = f"SELECT 1 FROM `{self.table_id}` WHERE document_id = @doc_id LIMIT 1"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("doc_id", "STRING", document_id)]
        )
        query_job = self.bq_client.query(query, job_config=job_config)
        return len(list(query_job.result())) > 0

    def process_document(self, gcs_uri: str) -> list[dict]:
        """Downloads, parses, chunks a document, and returns a list of chunk dicts."""
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
        
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            if not text.strip():
                continue
                
            for chunk_data in self.text_splitter.split_text(text):
                chunks_list.append({
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "chunk_data": chunk_data,
                    "gcs_uri": gcs_uri,
                    "filename": filename,
                    "structural_metadata": json.dumps({"title": filename, "page": page_num}),
                    "page_number": page_num,
                    "embedding": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "vectorized_at": None,
                })
        return chunks_list

    def stage_chunks_bq(self, chunks_list: list[dict]) -> None:
        """Stages chunks into BigQuery using batch load to bypass streaming buffer."""
        if not chunks_list:
            return
            
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        try:
            job = self.bq_client.load_table_from_json(chunks_list, self.table_id, job_config=job_config)
            job.result()
        except Exception as e:
            raise RuntimeError(f"BigQuery insertion errors: {e}")

    def move_blob_to_processed(self, gcs_uri: str) -> str:
        """Moves a blob from the ingested/ prefix to the processed/ prefix."""
        bucket_name = gcs_uri.replace("gs://", "").split("/")[0]
        blob_name = gcs_uri.replace(f"gs://{bucket_name}/", "")
        
        if "ingested/" not in blob_name:
            return gcs_uri
            
        new_blob_name = blob_name.replace("ingested/", "processed/", 1)
        bucket = self.storage_client.bucket(bucket_name)
        source_blob = bucket.blob(blob_name)
        
        bucket.copy_blob(source_blob, bucket, new_blob_name)
        source_blob.delete()
        
        return f"gs://{bucket_name}/{new_blob_name}"

    def run_staging(self, gcs_uri: str) -> int:
        """Orchestrates parsing and staging, returns the count of chunks stored."""
        chunks = self.process_document(gcs_uri)
        if chunks:
            self.stage_chunks_bq(chunks)
            self.move_blob_to_processed(gcs_uri)
        return len(chunks)

    def generate_embeddings(self, gcs_uri: str) -> bool:
        """Vectorizes staged chunks by joining with metadata and updating via BQML."""
        model_id = self.table_id.replace("documents_chunks", "multimodal_embedding_model")
        metadata_id = self.table_id.replace("documents_chunks", "documents_metadata")
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
            query_parameters=[bigquery.ScalarQueryParameter("gcs_uri", "STRING", gcs_uri)]
        )
        try:
            self.bq_client.query(query, job_config=job_config).result()
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to generate embeddings: {e}")
