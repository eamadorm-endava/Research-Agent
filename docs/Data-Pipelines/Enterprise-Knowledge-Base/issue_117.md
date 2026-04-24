# Issue 117: Automated RAG Pipeline Provisioning

As a developer engineer,
I want to provision a parameterized Cloud Function, the BigQuery ML integrations, and a Cloud Build CI/CD pipeline,
So that the entire RAG ingestion process (from chunking to BQ vectorization) can be flexibly triggered by providing a target GCS URI.

**Acceptance Criteria**

Compute Provisioning: Deploy a Cloud Function service v2 (backed by Cloud Run) using the Python 3.x runtime to host the end-to-end RAGIngestion application.
Flexible Trigger (Parameterized): The function must be configured with an HTTP trigger. It must accept a JSON payload containing the parameter {"gcs_uri": "gs://..."}.

USe the code we built for Issue_116 and Issue_118

IAM Configuration (Least Privilege): * Provision a dedicated service account for the Cloud Function.
Attach exact minimum roles required: Storage Object Viewer, BigQuery Data Editor, Vertex AI User, and BigQuery Connection User.
Restrict the function's invoker permissions so it is not publicly accessible.
CI/CD Pipeline: Create Cloud Build pipelines (e.g., cloudbuild.yaml) that execute unit tests, enforce the 60-lines-per-method constraint via automated linting, and automatically deploy the Terraform and Cloud Function upon merging to the main branch.

**Definition of Done**

Terraform code is fully modularized, reviewed, and cleanly applied without manual GCP Console interventions.
The Cloud Resource Connections are visible and active in the Google Cloud Console.
The Cloud Build pipeline runs green end-to-end, actively blocking PRs if the 60-line method limit or unit tests fail.
A live infrastructure integration test proves that sending a secure HTTP POST request containing a valid gcs_uri successfully triggers the function, resulting in the table documents_chunks being populated with the final vector embeddings fully generated.