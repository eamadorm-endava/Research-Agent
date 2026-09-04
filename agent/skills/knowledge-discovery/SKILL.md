---
name: knowledge-discovery
description: MANDATORY PROTOCOL for data retrieval and research. Trigger this skill whenever the user asks to "search", "find", "look up", "summarize", "investigate", or "retrieve" ANY information across enterprise, personal, collaborative, or communication tools. If the user asks about a project, person, topic, email, calendar event, ticket, document, or repository, you MUST follow this protocol before answering.
---

## Pre-Search Validation
Before proceeding, verify whether the user has clearly stated the target of the search.
**A query is considered unclear when it:**
- Expresses intent without a topic (e.g., "search everything", "conduct research", "look it up").
- Names only a source or tool, not a subject (e.g., "check the knowledge base", "query BigQuery", "search SharePoint").
- Is too vague to form a meaningful search (e.g., "find documents", "search for info").

**When the query is unclear**, execution must halt. Do not guess, infer, or proceed with a search. Respond EXACTLY with:
> "What topic, document, project, or information would you like me to search for?"

---

## Phase 0: Temporal & Entity Extraction
1. **Temporal Grounding**:
   - If current time context is not yet established in the session, use `get_current_time()` to ground date-sensitive, relative, or time-bounded queries (e.g., "last month", "recent meetings", "since June 2026").
2. **Entity Distillation**:
   - Extract primary subjects, project codes, ticket IDs, person names, client names, and technical terms.
   - Strip these down into **pure keywords of maximum 1 or 2 words** (e.g., extracting "Alpha" from "Project Alpha status report").
   - These distilled keywords MUST be used for all broad discovery tool parameters. NEVER use the raw conversational user prompt for keyword parameters.

---

## Phase 1: Massive Parallel Omni-Discovery
Fire discovery tools across all active MCP servers CONCURRENTLY in a single turn. 

You must dynamically identify and fire ALL available discovery tools that match the following regex patterns:
- `*_search_*` (for keyword-based searches)
- `*_list_*` (for broad sweeps or enumeration)
- `*_query_*` (for semantic queries)

**Parameter Mapping:**
- For any parameter expecting a `query`, `keyword`, or `search_term`, use the 1-2 word distilled keywords from Phase 0.
- For date or time bounds, default to a 6-month window ascending unless specified by the user.

---

## Phase 2: Relational Identity Graph & Cross-Search
Analyze the results returned from Phase 1.
1. **Relevance Filtering**: Discard keyword matches that are semantically irrelevant to the user's intent.
2. **Context Graph Extraction**: Extract associated entities:
   - **Ticket keys & Page IDs**: Jira issue keys, Confluence page IDs, SharePoint site IDs.
   - **Stakeholders & People**: Authors, assignees, participants, senders, reviewers.
   - **Organizations & Projects**: Client names, vendor names, repository names, technical tags.
3. **Secondary Targeted Search (If Needed)**:
   - If initial results yield partial information or reveal critical linked entities (e.g., an email mentions a Jira ticket key `PROJ-1234` or a specific file name), launch a quick targeted search for those specific identifiers in the respective tools.

---

## Phase 3: Selective Deep Reading (Need-to-Know Only)
Do NOT read entire document payloads or full email/event bodies if the snippet/metadata (`bodyPreview`, summary, description, schema) already satisfies the user's inquiry.

When deeper inspection is strictly required, execute deep-reading tools ONLY for the specific IDs or items discovered in Phase 1. You must dynamically identify and use tools matching the following patterns:
- `*_read_*` (for reading full content bodies)
- `*_get_*` or `*_details*` (for fetching metadata or specific details)

### Concurrency & Reading Guardrails
- **Max Concurrency Per Turn**: Maximum **5 deep-read tool calls** in a single turn.
- **Dynamic Max Per Source**:
  - Multi-source search: Maximum **2 deep files per data source**.
  - Single-source deep dive: Maximum **5 files** from that single source.
- **Max Loop Limit**: Maximum **8 internal iterations** before synthesizing findings.

---

## Phase 4: Executive Output Format
Structure your synthesized response using the markdown template below. **Do NOT include the "Executive Output Format" title in your response.**

### Formatting Guidelines
1. **STRICT NO-MONOLOGUE RULE**: Never output intermediate thoughts or conversational status logs (e.g., "I am reading Jira tickets"). Start immediately with `## Summary`.
2. **Calendar & Meetings**: If meetings are found (from Google Calendar or Outlook Calendar), render the "Upcoming Meetings" and "Previous Meetings" sections (name, description, attendees, organizer, meeting link, attachments). Omit these sections only if no calendar search was executed or no events exist.
3. **References Table**: Every relevant piece of evidence must be cited in the table. The `Source` column must display the human-readable platform name derived from the MCP tool (e.g., `EKB`, `Jira`, `Confluence`, `Google Drive`, `OneDrive`, `SharePoint`, `Google Calendar`, `Outlook Calendar`, `Outlook Email`, `BigQuery`, `Cloud Storage`).

### Output Template
```markdown
## Summary
[1–2 paragraphs. Crisp, executive overview of findings across all consulted data sources, answering the core question directly. No bullet points.]

## Key Findings
- [Bulleted list of the most critical facts, project statuses, technical decisions, and notable updates extracted from sources.]

## Action Items & Next Steps
- [Actionable follow-up item with designated owner and deadline if identified in sources.]

## Stakeholders & Contacts
- [Name (Role / Organization) - Email]

## Upcoming Meetings
[Meetings occurring after current date/time. Separate with `---`. Include: Name, Date/Time, Organizer, Attendees, Meeting Link, Attachments status.]

## Previous Meetings
[Meetings that occurred before current date/time. Separate with `---`. Include: Name, Date/Time, Organizer, Attendees, Meeting Link, Attachments status.]

## References
| Source | Project / Context | Item Name / Subject / Title | Owner / Author | Date / Last Update |
|:---:|:---:|:---:|:---:|:---:|
| [Source Name] | [Project/Domain] | [Filename / Email Subject / Ticket Key / Page Title] | [Owner Email / Assignee] | [YYYY-MM-DD] |
```

---

## Tool Naming Standard Enforcement
To successfully execute this skill, you rely on the consistent naming convention of MCP tools. If you are ever tasked with creating or modifying a new MCP tool for discovery or reading, you MUST ensure it follows the format: `[datasource]_[verb]_[entity]`.
- **Discovery verbs:** `search`, `list`, or `query`.
- **Reading verbs:** `read`, `get`, or `details`.
