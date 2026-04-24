import json
import uuid
import fitz
from google.cloud import storage

uid = uuid.uuid4().hex[:6]
filename = f"test_doc_{uid}.pdf"
gcs_uri = f"gs://kb-landing-zone-test/ingested/{filename}"

# Create and upload PDF
print(f"Creating and uploading dummy PDF: {filename}")
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "This is a fresh test document for vectorization.")
doc.save(filename)

client = storage.Client(project="ag-core-dev-fdx7")
bucket = client.bucket("kb-landing-zone-test")
blob = bucket.blob(f"ingested/{filename}")
blob.upload_from_filename(filename)

# Update notebook
path = "notebooks/enterprise_knowledge_base/rag_ingestion/rag_verification.ipynb"
with open(path, "r") as f:
    nb = json.load(f)

nb["cells"][4]["source"] = [
    "# Run the full pipeline (staging + vectorization)\n",
    f"GCS_URI = \"{gcs_uri}\"\n",
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
    f"WHERE gcs_uri = '{gcs_uri}'\n",
    "LIMIT 5\n",
    "\"\"\"\n",
    "\n",
    "results = bq_client.query(query).result()\n",
    "for row in results:\n",
    "     print(dict(row))"
]

# clear outputs
for cell in nb["cells"]:
    if "outputs" in cell: cell["outputs"] = []
    if "execution_count" in cell: cell["execution_count"] = None

with open(path, "w") as f:
    json.dump(nb, f, indent=1)

print("Notebook updated, running nbconvert...")
