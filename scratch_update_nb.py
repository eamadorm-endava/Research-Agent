import json
import fitz
from google.cloud import storage

# 1. Update the Notebook
path = "notebooks/enterprise_knowledge_base/rag_ingestion/rag_verification.ipynb"
with open(path, "r") as f:
    nb = json.load(f)

nb["cells"][2]["source"] = [
    "import sys\n",
    "import os\n",
    "sys.path.append(\"../../..\")\n",
    "from google.cloud import bigquery\n",
    "from pipelines.enterprise_knowledge_base.rag_ingestion import RAGIngestion\n",
    "from pipelines.enterprise_knowledge_base.orchestrator import KBIngestionPipeline"
]

nb["cells"][3]["source"] = [
    "# Initialize the pipeline orchestrator\n",
    "PROJECT_ID = \"ag-core-dev-fdx7\"\n",
    "pipeline = KBIngestionPipeline(project_id=PROJECT_ID)\n"
]

nb["cells"][4]["source"] = [
    "# Run the full pipeline (staging + vectorization)\n",
    "# Note: Replace with a real GCS URI available in your project\n",
    "GCS_URI = \"gs://kb-landing-zone-test/ingested/test_doc_for_embeddings.pdf\"\n",
    "\n",
    "try:\n",
    "    pipeline.trigger_pipeline(GCS_URI)\n",
    "except Exception as e:\n",
    "    print(f'Pipeline execution result: {e}')"
]

nb["cells"][5]["source"] = [
    "# Verify BigQuery: Check if embeddings were generated\n",
    "bq_client = bigquery.Client(project=PROJECT_ID)\n",
    "query = f\"\"\"\n",
    "SELECT chunk_id, gcs_uri, ARRAY_LENGTH(embedding) as embedding_length \n",
    "FROM `{PROJECT_ID}.knowledge_base.documents_chunks` \n",
    "WHERE gcs_uri = '{GCS_URI}'\n",
    "LIMIT 5\n",
    "\"\"\"\n",
    "\n",
    "results = bq_client.query(query).result()\n",
    "for row in results:\n",
    "     print(dict(row))"
]

for cell in nb["cells"]:
    if "outputs" in cell:
        cell["outputs"] = []
    if "execution_count" in cell:
        cell["execution_count"] = None

with open(path, "w") as f:
    json.dump(nb, f, indent=1)
    
print("Notebook updated successfully.")

# 2. Upload a dummy PDF so the notebook can run without FileExistsError or NotFound
print("Creating and uploading dummy PDF...")
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "This is a test document to verify the vectorization and embedding generation process.")
doc.save("test_doc_for_embeddings.pdf")

try:
    client = storage.Client(project="ag-core-dev-fdx7")
    bucket = client.bucket("kb-landing-zone-test")
    blob = bucket.blob("ingested/test_doc_for_embeddings.pdf")
    blob.upload_from_filename("test_doc_for_embeddings.pdf")
    print("Dummy PDF uploaded to gs://kb-landing-zone-test/ingested/test_doc_for_embeddings.pdf")
except Exception as e:
    print(f"Failed to upload dummy PDF: {e}")
