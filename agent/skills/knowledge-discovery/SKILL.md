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
    -   **People**: `uploader_email` and key stakeholders mentioned in descriptions.
    -   **Locations**: `gcs_uri` (essential for technical deep-dives).
3.  **Expansion**: If results are narrow, broaden the search using the extracted entities and keywords to find related entries before moving to Phase 2.

### Phase 2: Parallel Context Acquisition (Broad Search)
Maximize information gathering by querying multiple sources in parallel. 
*Efficiency Rule: Limit to a maximum of 2 concurrent requests per data source. DO NOT repeat the same tool call with the same parameters in the same session. Aim to find core data in the first turn.*

1.  **Calendar (Temporal Context)**:
    -   **MANDATORY**: The **first call** to `list_calendar_events` MUST ONLY include the date range filter (1 month past - 1 month future). Do not include title or description filters initially.
    -   **Internal Filtering**: Once retrieved, analyze results for matches in titles, descriptions, and the names of **attached files** using the anchors from Phase 1.
    -   **Awareness**: Flag relevant attachments and meeting context for potential Phase 3 analysis, but do not read their content yet.
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
    -   Use `gcs_read_file` or equivalent tools to analyze the full content of high-relevance `gcs_uri` references found in Phase 1 and 2.
    -   Prioritize technical specifications, architecture diagrams, and project charters stored in EKB.
2.  **Level 2: Drive Deep-Dive**:
    -   If Level 1 is insufficient, proceed to search and read the full content of relevant Google Drive documents found in Phase 2.
    -   Focus on collaborative docs, meeting notes, and spreadsheets that might contain the specific missing detail.
3.  **Level 3: Final Conclusion**:
    -   If the information is not found after both deep-dives, concisely state that the specific data was not found in the available Enterprise Knowledge Base or personal Drive. Do not hallucinate or guess.

### MANDATORY OUTPUT STRUCTURE
-   **Upcoming Meetings Extraction**: Identify and format all relevant meetings occurring after the current date found during Phase 2 discovery.
-   **Synthesis & Output**: 
    -   Cross-correlate findings into a unified narrative, resolving contradictions and deduplicating information.
    -   **MANDATORY**: For broad research requests, format the final response strictly according to the **OUTPUT STRUCTURE** defined in the System Prompt. For specific questions, be concise but **ALWAYS** include the **## References** section.
