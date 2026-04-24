import os
import functions_framework
from flask import Request, jsonify
from pipelines.enterprise_knowledge_base.orchestrator import KBIngestionPipeline

@functions_framework.http
def rag_ingestion_http(request: Request):
    """HTTP Cloud Function for RAG Ingestion pipeline."""
    request_json = request.get_json(silent=True)
    if not request_json or 'gcs_uri' not in request_json:
        return jsonify({"error": "Missing 'gcs_uri' in payload"}), 400

    gcs_uri = request_json['gcs_uri']
    project_id = os.environ.get('PROJECT_ID')
    
    if not project_id:
        return jsonify({"error": "PROJECT_ID environment variable is not set"}), 500

    try:
        pipeline = KBIngestionPipeline(project_id=project_id)
        pipeline.trigger_pipeline(gcs_uri)
        return jsonify({"message": f"Successfully processed {gcs_uri}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
