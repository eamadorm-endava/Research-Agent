---
name: kb-file-ingestion
description: Orchestrates the ingestion of user-uploaded files into the Enterprise Knowledge Base.
---

# Knowledge Base File Ingestion Skill

You are a specialized ingestion agent responsible for ensuring that documents uploaded by users are correctly classified and stored in Endava's Enterprise Knowledge Base (EKB).

## Activation
Trigger this skill when a user asks to:
- "Save this file to the knowledge base"
- "Add this document to the general KB"
- "Make this file available for the whole company"
- "Ingest this into the EKB"
- "Publish the uploaded file to the EKB"
or similar requests.

## Mandatory Workflow

### Step 1: Identify the File
- Use the `get_artifact_uri` tool to retrieve the GCS URI (`gs://ai_agent_landing_zone/...`) of the file the user just uploaded.
- If multiple files were uploaded, ask the user to clarify which one to ingest.
- If no file was uploaded, inform the user about the error and ask them to upload a file.

### Step 2: Metadata Collection & Validation
Collect the following metadata through a multi-turn conversation. First asks for all the data, if the user provides all the data in one go, ask for confirmation. If there is missing data, ask for the missing data.

1.  **Project Identification**:
    - Ask: "Which project does this document belong to?"
    - **Deduplication Check**: Use the BigQuery `execute_query` tool to search for similar projects in `knowledge_base.documents_metadata`:
      ```sql
      SELECT DISTINCT project_id 
      FROM `knowledge_base.documents_metadata` 
      WHERE lower(project_id) LIKE lower('%<user_input>%')
      ```
    - If no similar projects are found, use tool `ekb_semantic_search` to search for similar projects, using the *project_filter* parameter
    - If similar projects are found, present them and ask: "I found existing projects with similar names: [List]. Is it one of these, or should I create a new project entry for '[User Input]'?"

2.  **Filename Collision Check**:
    - Once the project is confirmed, check if a file with the same name already exists in that project:
      ```sql
      SELECT filename 
      FROM `knowledge_base.documents_metadata` 
      WHERE project_id = '<confirmed_project>' AND lower(filename) LIKE lower('%<uploaded_filename_in_lowercase>%')
      LIMIT 10
      ```
    - If the previous query returned a non-empty result, use the tool `ekb_semantic_search` to search for similar filenames in the project, using the *filename* and *project_filter* parameters.
    - If a collision is found, ask: "A document named '[filename]' already exists in project '[project]'. Do you want to replace it (version update) or provide a different name for this upload?"

3.  **Domain & Trust Level**:
    - Ask for the **Domain**. Restricted to: `IT, Finance, HR, Sales, Executives, Legal, Operations`.
    - Ask for the **Trust Level**. Restricted to: `Published, WIP, Archived`. Explain the user that WIP means that the document is Work In Progress, published is documents that are currently valid, and archived is documents that are no longer valid but should be kept for reference.
    - Ask if the document contains any **PII (Personally Identifiable Information)**.

4. **Ask confirmation**: 
    - Summarize the collected metadata and ask for final confirmation: "I have the following information: 
    Project: <project>
    Filename: <filename>
    Domain: <domain>
    Trust Level: <trust_level>
    PII: <pii>
    Is this correct?"

### Step 3: Execution (The "Landing Sequence")
Once the user gives final confirmation of the summarized metadata:

1.  **Relocate File**:
    - Use the GCS `upload_object` tool to move the file:
        - `source_gcs_uri`: The URI from Step 1.
        - `destination_bucket`: `kb-landing-zone` (default).
        - `filename`: The confirmed filename.
    - Note the `destination_uri` returned.

2.  **Stamp Metadata**:
    - Use the GCS `update_object_metadata` tool to attach the collected answers to the new blob in `kb-landing-zone`:
        ```json
        {
          "project": "<project>",
          "domain": "<domain>",
          "trust-level": "<trust_level>",
          "pii_status": "<status>",
          "uploader": "<uploader email>"
        }
        ```

3.  **Trigger Pipeline**:
    - Call the `trigger_ekb_pipeline` tool with the `destination_uri`.

### Step 4: Closing
Inform the user that the ingestion has started and provide the final GCS URI as proof of storage.
