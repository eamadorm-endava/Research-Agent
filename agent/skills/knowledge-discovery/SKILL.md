---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval and analysis using Contextual Anchoring and Parallel Discovery.
---

## Mandatory Execution Mode
Trigger this skill for any research task or when the user's query is broad or vague. Use this to establish a factual baseline across all data sources.

## Discovery Protocol

### Phase 1: Contextual Anchoring (The Hook)
1.  **Semantic Search**: Execute `ekb_semantic_search`.
2.  **Anchor Extraction**: Build a "Context Graph" from the results:
    -   **Identities**: `project_name`, `project_id`, `document_id`, and `filename`.
    -   **Context**: Capture the `document_summary` or `description`. These snippets are vital for identifying additional keywords for Phase 2.
    -   **Entities**: Company names (clients/partners), technologies, and technical stacks.
    -   **Relational Mapping**: If a company is identified, immediately pivot to find the projects they are involved in. Use these project names as primary anchors for Phase 2 discovery across all sources.
    -   **People**: `uploader_email` and key stakeholders mentioned in descriptions.
    -   **Locations**: `gcs_uri` (essential for technical deep-dives).
3.  **Expansion**: If results are narrow, broaden the search using the extracted entities and keywords to find related entries before moving to Phase 2.

### Phase 2: Parallel Context Acquisition (Broad Search)
Maximize information gathering by querying multiple sources in parallel. 
*Efficiency Rule: Limit to a maximum of 2 concurrent requests per data source. DO NOT repeat the same tool call with the same parameters in the same session. Aim to find core data in the first turn.*

1.  **Calendar (Broad Temporal Discovery)**:
    -   **MANDATORY BASELINE**: Whenever searching for context related to entities (Projects, Companies, Tech Stacks), you MUST perform two separate requests to establish a broad temporal baseline:
        -   **Request 1 (Past)**: From [Current Date - 1 Month] to [Current Date]. Use `sort_order="desc"` to retrieve the nearest past events.
        -   **Request 2 (Future)**: From [Current Date] to [Current Date + 1 Month]. Use `sort_order="asc"` to retrieve the nearest upcoming events.
    -   **MANDATORY RESTRICTION**: In these first two requests, you MUST NOT include any parameters other than date filters and `sort_order`. 
    -   **Relational Mapping**: Once all events in the window are retrieved, perform internal filtering to identify events related to the projects or companies found in Phase 1 (EKB).
2.  **BigQuery (Structural Context)**:
    -   **MANDATORY**: Query the `documents_metadata` table inside the `knowledge_base` dataset.
    -   **Data Capture**: Retrieve and store all metadata, especially the **document summary/description**, linked to the identified project, domain, or company.
3.  **Google Drive (Personal Context)**:
    -   **Best Practice**: Perform searches using **single keywords** or very short phrases (e.g., search "Alpha" instead of "Project Alpha"). This avoids missing files with naming variations like "Alpha Follow-up" or "Project Continuation - Alpha".
    -   **Keywords**: Use company names, technologies, stacks, and project names found in Phase 1.
4.  **GCS (Raw Data Reference)**:
    -   Identify and store specific `gcs_uri` references for high-relevance files found in the metadata.

### Phase 3: Synthesis & Targeted Deep Dive (Escalation Path)
If high-level summaries or metadata are insufficient for a comprehensive answer, follow this strict escalation order:

1.  **Level 1: EKB Deep-Dive (GCS)**:
    -   Use `read_object` to retrieve metadata (specifically the `mime_type`) and then `import_gcs_to_artifact` to analyze the full content of high-relevance `gcs_uri` references found in Phase 1 and 2.
    -   Prioritize technical specifications, architecture diagrams, and project charters stored in EKB.
2.  **Level 2: Calendar Deep-Dive (Personal Context)**:
    -   Identify any **documents or links** mentioned in the descriptions or attachments of relevant past meetings found in Phase 2.
    -   Search for and read the content of these specific documents (using Drive or GCS tools) to capture meeting decisions, notes, or referenced data.
3.  **Level 3: Drive Deep-Dive**:
    -   If the information is still missing, use `get_file_text` to search and read the full content of relevant Google Drive documents found in Phase 2 discovery.
4.  **Level 4: Relationship Fallback (Implicit Mapping)**:
    -   If direct project/company links are missing, analyze EKB metadata (descriptions, summaries, and tech stacks) for shared technologies, industry themes, or generalities.
    -   Use these broader themes to re-evaluate the broad results found in Phase 2 (Calendar/Drive) to identify high-fidelity implicit relationships.
5.  **Level 5: Final Conclusion**:
    -   If the information is not found after all deep-dives (including implicit mapping), concisely state that the specific data was not found in the available Enterprise Knowledge Base or personal Drive. Do not hallucinate or guess.

### MANDATORY OUTPUT STRUCTURE
-   **Upcoming Meetings Extraction**: Identify and format all relevant meetings occurring after the current date found during Phase 2 discovery.
-   **Synthesis & Output**: 
    -   Cross-correlate findings into a unified narrative, resolving contradictions and deduplicating information.
    -   **STRICT REFERENCE RULE**: In your final `## References` section, you MUST ONLY include the specific files and events from which data was explicitly extracted. Do NOT include broad discovery results or unused tool outputs.
    -   **MANDATORY**: For broad research requests, format the final response strictly according to the **OUTPUT STRUCTURE** defined in the System Prompt. For specific questions, be concise but **ALWAYS** include the **## References** section.