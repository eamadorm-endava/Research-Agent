---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval and analysis using a hybrid RAG + Long Context approach.
---

## Mandatory Execution Mode

Trigger this skill when a user asks for broad research or specific analysis of a project, company, technology, or person within the enterprise.
Examples:
- "Tell me everything we know about project X"
- "Give me the current state of project Y"
- "Which projects use technology Z?"
- "Analyze the stakeholders for project K"

## Hybrid Discovery Protocol (3 Phases)

### Phase 1: Semantic Anchoring
1.  **Initial Search**: Call `ekb_semantic_search(project_id='ag-core-dev-fdx7', query='<user_query>')` to find conceptually relevant chunks and metadata.
2.  **Metadata Extraction**: Identify the following from the top results:
    - `project_id`
    - `domain`
    - `uploader_email` (Stakeholder)

### Phase 2: Metadata-based SQL Pivot
1.  **Broad Discovery**: Once a `project_id` or `domain` is identified, execute a targeted BigQuery SQL query to retrieve all related documents:
    ```sql
    -- Use execute_query(project_id='ag-core-dev-fdx7', query='...')
    SELECT filename, gcs_uri, description, uploader_email, ingested_at
    FROM `knowledge_base.documents_metadata`
    WHERE (project_id = '<identified_project>' OR domain = '<identified_domain>')
      AND latest = TRUE
    ORDER BY ingested_at DESC
    ```
2.  **Synthesis**: Use the `description` (document summary) from the metadata to form a high-level understanding of the project's scope and history.

### Phase 3: Long Context Deep Analysis (Conditional)
1.  **Trigger**: If the BigQuery metadata summaries are insufficient to answer the user's specific request or if deep analysis is required.
2.  **Selection**: Identify up to **10** most relevant GCS URIs from the SQL results.
3.  **Loading**: 
    - For each selected URI:
        - Call `import_gcs_to_artifact(gcs_uri='<uri>')` to register it as a session artifact.
    - Call `load_artifacts(filenames=['<filename1>', '<filename2>', ...])` to load the full content into the LLM context.
4.  **Analysis**: Perform the final analysis using the full document data.

## Standardized Output Format

All discovery responses must follow this structure:

### Summary
[1-2 paragraphs summarizing the context and findings]

### Key Points
- [Bullet 1]
- [Bullet 2]
- [Bullet N...]

### Stakeholders
- [Stakeholder Name/Role 1]
- [Stakeholder Name/Role 2]

### Data Sources
- [Filename] (Last Update: [Date], Owner: [Email/Name])
- [Filename] (Last Update: [Date], Owner: [Email/Name])

---

## Post-Discovery Interaction
After presenting the EKB findings, **ALWAYS** ask:
"I have completed the search in the Enterprise Knowledge Base. Would you like me to also search your personal data for additional context? If so, do you have a preference (Drive, personal buckets, or private BQ tables)? Searching across all sources may take some time."
