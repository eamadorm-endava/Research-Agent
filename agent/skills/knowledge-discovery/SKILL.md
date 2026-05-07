---
name: knowledge-discovery
description: Expert protocol for high-fidelity data retrieval and analysis using Contextual Anchoring and Parallel Discovery.
---

## Mandatory Execution Mode
Trigger this skill for any research task or when the user's query is broad or vague. Use this to establish a factual baseline across all data sources.

## BigQuery Query Protocol
This protocol applies **every time** you are about to call `execute_query`, regardless of which phase you are in.

1.  **Discover tables** (skip if already done this session for the same dataset): Call `list_tables` to confirm which tables exist inside the target dataset.
2.  **Fetch and cache schema** (skip if already fetched this session for the same table): Call `get_table_schema` for each table you intend to query. Store the returned field names and types in your working memory — do **not** call `get_table_schema` again for the same table later in the same session.
3.  **Construct the query**: Build the SQL using only column names confirmed in step 2. Never guess column names.
4.  **Execute**: Call `execute_query` with the validated query.

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
    -   **Zero-Result Fallback**: If `ekb_semantic_search` returns no results at all, do not stop. Extract keywords directly from the user's original prompt (company names, project names, technologies, people, dates) and use those as Phase 2 anchors for Drive and Calendar. Skip the BigQuery `documents_metadata` query in this case — there is no project context to anchor it against.

### Phase 2: Parallel Context Acquisition (Broad Search)
Maximize information gathering by querying multiple sources in parallel. 
*Efficiency Rule: Limit to a maximum of 2 concurrent requests per data source. DO NOT repeat the same tool call with the same parameters in the same session. Aim to find core data in the first turn.*

1.  **Calendar (Broad Temporal Discovery)**:
    -   **MANDATORY BASELINE**: Whenever searching for context related to entities (Projects, Companies, Tech Stacks), you MUST perform two separate requests to establish a broad temporal baseline:
        -   **Request 1 (Past)**: From [Current Date - 1 Month] to [Current Date]. Use `sort_order="desc"` to retrieve the nearest past events.
        -   **Request 2 (Future)**: From [Current Date] to [Current Date + 1 Month]. Use `sort_order="asc"` to retrieve the nearest upcoming events.
    -   **MANDATORY RESTRICTION**: In these first two requests, you MUST NOT include any parameters other than date filters and `sort_order`. 
    -   **Relational Mapping**: Once all events in the window are retrieved, perform internal filtering to identify events related to the projects or companies found in Phase 1 (EKB).
    -   **Targeted Follow-up** (only if the broad baseline returns no relevant events): Apply specific parameters — a `query` string using entity names from Phase 1, or keywords extracted directly from the user's original prompt if Phase 1 returned nothing, a wider date window (±2–3 months), or attendee filters. **Maximum 3 additional targeted attempts.** After 3 attempts without a useful result, stop and move to Phase 3.
2.  **BigQuery (Structural Context)**:
    -   **MANDATORY**: Follow the BigQuery Query Protocol above before querying. Target the `documents_metadata` table inside the `knowledge_base` dataset.
    -   **Data Capture**: Retrieve and store all metadata, especially the **document summary/description**, linked to the identified project, domain, or company.
3.  **Google Drive (Personal Context - Two-Wave Parallel Search)**:
    -   **Keyword Extraction**: Collect all useful nouns from Phase 1 anchors and the user's original prompt — project names, company names, technologies, people, product names, and other domain-specific terms. **Always exclude intent words like "duration", "status", or "summary"**.
    -   **Wave 1 — Single-word searches (run in parallel)**: Execute up to 3 `list_files` requests simultaneously, each using a different single keyword (e.g., `"Innovation"`, `"Alpha"`, `"Gemini"`). Prioritize the most distinctive nouns: project name first, then company name, then any other relevant keyword. If no relevant files are found by name, retry with 3 new different single-word keywords. Repeat up to **2 rounds maximum** before moving to Wave 2.
    -   **Wave 2 — Two-word fallback (run in parallel, only if Wave 1 returns no relevant filenames after all rounds)**: Combine the most relevant single keywords into 2-word phrases (e.g., `"Innovation Inc"`, `"Project Alpha"`) and execute up to 3 `list_files` requests simultaneously, each using a different phrase. If no relevant files are found by name, retry with 3 new different 2-word phrases. Repeat up to **2 rounds maximum**.
    -   **Exclusion Rule**: Never use intent keywords (e.g., "duration", "project length", "status") in any search. Focus on nouns that likely appear in filenames.
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
3.  **Level 3: Drive Iterative Discovery**:
    -   **Step 1 (Read)**: Use `get_file_text` to read the top 3 most relevant files found in Phase 2.
    -   **Step 2 (Evaluate)**: If the information is found, stop and synthesize.
    -   **Step 3 (Pivot & Repeat)**: If not found, extract new keywords from the text read (e.g., project codes, aliases, or stakeholders) and perform a new parallel search (Step 1).
    -   **Constraint**: Repeat this loop a maximum of 3 times. Ensure each search uses unique keywords to avoid redundant results.
4.  **Level 4: Relationship Fallback (Implicit Mapping)**:
    -   If direct project/company links are missing, analyze EKB metadata (descriptions, summaries, and tech stacks) for shared technologies, industry themes, or generalities.
    -   Use these broader themes to re-evaluate the broad results found in Phase 2 (Calendar/Drive) to identify high-fidelity implicit relationships.
5.  **Level 5: Final Conclusion**:
    -   Produce the standard output structure with `No information found` under any section where data is missing.
    -   **MANDATORY**: Your response MUST include the `## Extend Search?` section defined at the end of the MANDATORY OUTPUT STRUCTURE. This section is not optional at Level 5 — if it is missing, the task is incomplete.
    -   Do not continue searching without the user's input. Do not hallucinate.

### MANDATORY OUTPUT STRUCTURE
Before writing the response, classify the question:
-   **Concise Mode**: the question has a clear, narrow answer (a single fact, name, date, count, status, or yes/no). Use this mode for targeted lookups.
-   **Full Report Mode**: the answer requires synthesizing information across multiple sources, documents, or time periods. Use this mode for broad or exploratory research.

---

#### Concise Mode
Respond directly in plain prose (1–3 sentences). Then append only the `## References` table (see format below). Skip all other sections.

---

#### Full Report Mode
Cross-correlate all findings into a unified narrative before writing the response. Follow this exact section order. Omit a section only if genuinely no data exists for it — in that case write `No information found` under that heading, do not skip the heading entirely.

**Summary** *(always present)*
1–2 paragraphs. Brief context of what was found, the topic, and its relevance. No bullet points here.

---

**## Key Points**
Bullet list of the most important facts, decisions, dates, and findings extracted from the sources.

---

**## Stakeholders**
Bullet list of people involved: name, role or relationship to the topic, and contact email when available.

---

**## Upcoming Meetings**
List ONLY meetings occurring after the current date that are directly related to the project, company, or topic the user asked about. For each entry include: date, time, title, and participants.
If none found: `No upcoming meetings found for this topic.`

---

**## Previous Meetings**
List meetings from the 1-month past window (Phase 2 Calendar broad search) that are related to the project, company, or topic the user asked about. For each entry include: date, title, and key participants.
If none found: `No recent meetings found for this topic.`

---

**## Extend Search?** *(include ONLY when Level 5 is reached — all standard sources exhausted with no relevant results)*
Begin with one sentence stating which sources were searched and what terms were used. Then include this question verbatim:

> "I have searched the Enterprise Knowledge Base, Google Calendar, and Google Drive using the available context and found no matching data. Would you like me to extend the search to your personal GCS buckets or BigQuery tables? If yes, please share the bucket name, path prefix, or table/dataset identifier and I will search there directly."

This section MUST appear after `## References` at Level 5. Omitting it when Level 5 is reached means the task is incomplete.

---

**## References** *(both modes)*
Markdown table. Include ONLY the files, documents, and events from which data was explicitly extracted to produce this response. NEVER include broad discovery results or unused tool outputs.

| Source | Filename | Owner | Created at / Last Update |
|:---:|:---:|:---:|:---:|
| EKB / Drive / Cloud Storage / BigQuery (`dataset.table`) | Human-readable file or event name | Author email or display name | `YYYY-MM-DD` |

-   **Source**: one of `EKB`, `Drive`, `Cloud Storage`, or `BigQuery (dataset.table)` — use the most specific label, e.g. `BigQuery (knowledge_base.documents_metadata)`.
-   **Filename**: human-readable name or event title. NEVER show raw IDs, hashes, or GCS URIs.
-   **Owner**: uploader email, document owner, or event organizer. Use `Unknown` if unavailable.
-   **Created at / Last Update**: `YYYY-MM-DD`. Use `Unknown` if unavailable.