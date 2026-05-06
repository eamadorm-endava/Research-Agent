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
*Efficiency Rule: Limit to a maximum of 3 concurrent requests per data source. Aim to find core data in the first turn.*

1.  **Calendar (Temporal Context)**:
    -   **MANDATORY**: The **first call** to `list_calendar_events` MUST ONLY include the date range filter (±3 months). Do not include title or description filters initially.
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

### Phase 3: Synthesis & Targeted Deep Dive
If high-level summaries are insufficient for a comprehensive answer:
1.  **Multisource Ingestion**: Import and load content from:
    -   Specific **GCS URIs** (using `import_gcs_to_artifact`).
    -   **Google Drive** files and **Calendar Attachments** flagged in Phase 2.
2.  **Cross-Correlation**: Synthesize findings into a unified narrative, resolving contradictions and deduplicating information.
