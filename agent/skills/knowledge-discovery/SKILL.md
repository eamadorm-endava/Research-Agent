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
1.  **Initial Search**: Call the `ekb_semantic_search` tool using the `query` parameter and the other mandatory parameters.
    - **MANDATORY**: Strictly follow the tool's input schema definition (e.g., nesting parameters under a `request` object).
2.  **Metadata Extraction**: Identify the following from the top results:
    - `project_id`
    - `domain`
    - `document_id`
    - `uploader_email` (Stakeholder)
    - `latest` (Boolean)

### Phase 2: Metadata-based SQL Pivot
1.  **Broad Discovery**: Once identifiers are found, call `execute_query` to retrieve all related documents.
    - **MANDATORY**: Strictly follow the tool's input schema definition.
    - **Example Query Pattern**:
    ```sql
    SELECT filename, gcs_uri, description, uploader_email, ingested_at, latest
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
        - Call `import_gcs_to_artifact` using the `gcs_uri`.
    - Call `load_artifacts` using the `filenames` list.
    - **MANDATORY**: Strictly follow each tool's input schema definition.
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
