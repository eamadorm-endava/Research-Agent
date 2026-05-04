---
name: kb-file-ingestion
description: Orchestrates the ingestion of user-uploaded files into the Enterprise Knowledge Base.
---

## Mandatory execution mode

Trigger this skill when a user asks to:
- "Save this file to the knowledge base"
- "Add this document to the general KB"
- "Make this file available for the whole company"
- "Ingest this into the EKB"
- "Publish the uploaded file to the EKB"
- "Upload the file to the database"
- "Register this document in EKB"
- "Upload it to KB"
or similar requests.

## Progress Tracker
Maintain this state throughout the interaction:
- [ ] Step 1: Identify and verify session artifact
- [ ] Step 2: Collect metadata and validate project (Deduplication)
- [ ] Step 3: Relocate file and stamp metadata
- [ ] Step 4: Trigger EKB Pipeline

## Gotchas
- **GCS URIs**: The agent landing zone is always `gs://ai_agent_landing_zone/`. 
- **KB Landing Zone**: The KB ingestion bucket is **`gs://ag-core-dev-fdx7-kb-landing-zone/`**. You MUST use this exact name for the `destination_bucket` to trigger the Service Account authentication switch.
- **Project IDs**: In BigQuery, `project_id` is case-sensitive in some operations but should be checked case-insensitively for duplicates.
- **Job IDs**: Always return the `job_id` from the pipeline response to the user as a confirmation.
- **Proactive Notifications**: The agent core automatically checks pending `job_id`s before every response. You do not need to poll manually; a system update will appear in your history once the job is finished.

## Mandatory Workflow

### Step 1: Identify and Validate the File
1.  Use the `get_artifact_uri` tool to find the URI of the file the user just uploaded.
2.  **Validation**:
    - **File Type**: Ensure the file is a **PDF**. If it is not a PDF (e.g., `.docx`, `.txt`), inform the user: "Endava's Knowledge Base only accepts PDF documents. Please convert your file to PDF and upload it again to continue."
    - **Multi-file**: If multiple PDF files exist, ask: "I see several PDFs ([List]). Which one should I ingest?"
    - **Missing**: If no PDF file is found, ask: "Please upload the PDF document you'd like to add to the knowledge base."

### Step 2: Information Gathering & Validation
To minimize turns, **ALWAYS** ask for all necessary information in a single bulleted message immediately after Step 1:

"Before storing the file, please provide me the following information:
- **project the file belongs to**:
- **domain**: (Options: `IT, Finance, HR, Sales, Executives, Legal, Operations`)
- **trust-level**: (Options: 
    - `Published`: Document is currently valid and verified.
    - `WIP`: Work in progress, potentially incomplete.
    - `Archived`: No longer valid, kept for reference only.)
- **PII Status**: Does this document contain any Personally Identifiable Information?"

**Once the user provides the information, perform the following in sequence:**

1.  **Semantic Project Validation**: Use `ekb_semantic_search(query='<user_input_project_name>')`.
    - If a high-confidence match exists, proceed with that `project_id`.
    - If ambiguous, ask: "I found existing projects that might match: [List]. Is it one of these?"
2.  **Deduplication Check**: If the project exists, check for duplicate filenames and retrieve their existing metadata:
    ```sql
    SELECT filename, domain, classification_tier 
    FROM `knowledge_base.documents_metadata` 
    WHERE project_id = '<confirmed_project>' AND lower(filename) = lower('<uploaded_filename>')
      AND latest = TRUE
    ```
    - If found, ask: "A version of '<filename>' already exists. Should I replace it or would you like to rename this file?"
    - **MANDATORY**: If the user chooses to **REPLACE** the file, you MUST reuse the `domain` and `classification_tier` retrieved from the existing record for the new ingestion.
3.  **Final Summary**: Confirm the final metadata values with the user before proceeding to Step 3.

### Step 3: Relocation & Stamping
1.  **Move File**: Use `upload_object` (from GCS MCP) to copy the file using these parameters:
    - `source_gcs_uri`: The URI identified in Step 1.
    - `destination_bucket`: "ag-core-dev-fdx7-kb-landing-zone"
    - `filename`: The confirmed filename.
    - `path_inside_bucket`: The confirmed `<project_id>`.
    - **Note**: The relocation process automatically preserves the source metadata.
2.  **Stamp Metadata**: Use `update_object_metadata` (GCS) to attach the following. This will be **merged** with existing metadata:
    ```json
    {
      "project": "<project>",
      "domain": "<domain>",
      "trust-level": "<trust_level>",
      "pii_status": "<status>"
    }
    ```

### Step 4: Trigger Pipeline
1.  Call `trigger_ekb_pipeline(gcs_uri='<destination_uri_returned_in_Step_3>')`.
    - **Note**: This MUST be exactly the same URI returned by the `upload_object` tool.
2.  **Final Confirmation**: Provide the user with a summary using this template:
    ```markdown
    ### ✅ Ingestion Started
    - **File**: <filename>
    - **Project**: <project_id>
    - **Job ID**: <job_id_from_tool>
    - **Status**: The document is being processed and will be available in the KB shortly.
    ```
