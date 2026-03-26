---
name: meeting-summary
description: create, retrieve context for, and store standardized meeting summary documents for a specific meeting. use when a user asks to summarize a named meeting, summarize a recent meeting with identifiable context, generate a follow-up meeting recap, or save a meeting summary into the user's drive folder. especially use when mcp drive server is available and the agent must search drive for transcripts, related documents, and upload the finished summary from a template.
---

# Meeting Summary

Create a standardized meeting summary document for one specific meeting and save it into the user's Drive.

## Workflow

1. Identify the target meeting.
2. Gather meeting evidence from MCP Drive Server first.
3. If available, gather extra context for follow-up meetings from related Drive files.
4. Extract the summary fields.
5. Generate the summary document from the template in `assets/meeting-summary-template.docx`.
6. Save the file into `AI Meetings Summaries` or the closest equivalent folder in the user's Drive.
7. Report back with the document name, save location, and any missing data.

## 1) Identify the target meeting

Work on one meeting only.

Collect or infer these identifiers from the user's request and available Drive evidence:
- meeting name
- meeting date
- customer, project, or account name
- likely transcript or notes filename

If several meetings could match, choose the best-supported match and say which one you used.

## 2) Retrieve meeting evidence

Use MCP Drive Server as the primary source.

Search Drive for:
- transcript files
- meeting notes
- agendas
- slide decks
- follow-up notes
- action-item docs
- emails or exported notes stored in Drive

Prioritize files whose names or contents match the meeting name and date.

Preferred evidence order:
1. verbatim transcript
2. official meeting notes
3. agenda plus follow-up notes
4. related project docs that clarify context

Capture these fields when available:
- meeting name
- meeting date
- participants
- transcript text or strongest available notes
- future session date
- related documents that would be useful to attach or mention

## 3) Handle follow-up meetings

Treat the meeting as a follow-up when the transcript or filename suggests this is a review, sync, checkpoint, weekly call, status meeting, second session, next session, or continuation.

For follow-up meetings, search Drive for earlier summaries or earlier meeting materials for the same customer, project, or meeting series. Use prior files only to improve context. Do not invent facts that are absent from the current meeting evidence.

## 4) Extract the required summary

Fill these sections in the final document:
- Date of the meeting
- Meeting name
- Main Purpose
- Participants
- Conclusions / Main comments
- Next steps
- Date of the future session
- Documents that could be useful

Extraction rules:
- Derive **Main Purpose** as a short paragraph or 2 to 4 bullets explaining why the meeting happened.
- Summarize **Conclusions / Main comments** as the most important discussion points, decisions, blockers, and notable comments.
- Summarize **Next steps** as action-oriented bullets with owners only when the evidence clearly supports the owner.
- Use `Not found in available sources` for missing required fields.
- Never fabricate participants, dates, decisions, or commitments.
- Keep the summary factual and concise.

## 5) Generate the document from the template

Use the template file in `assets/meeting-summary-template.docx`.

Populate the placeholders and preserve this section order:
1. Date of the meeting
2. Meeting name
3. Main Purpose
4. Participants
5. Conclusions / Main comments
6. Next steps
7. Date of the future session
8. Documents that could be useful

Document writing rules:
- Use clean business language.
- Prefer bullets for conclusions and next steps.
- For participants, use a comma-separated list or bullets depending on what fits the template.
- For useful documents, list Drive file names and, when available, short context for why each file matters.

## 6) Standardize the output filename and folder

Save the generated file in a Drive folder named `AI Meetings Summaries`.

Folder behavior:
- If `AI Meetings Summaries` exists, use it.
- Otherwise create `AI Meetings Summaries`.
- If creation is blocked, save in the nearest user-approved equivalent and explicitly say so.

Filename format:
`YYYY-MM-DD - <meeting name> - Meeting Summary.docx`

Filename normalization rules:
- Use the meeting date from the source meeting. If unavailable, use `undated`.
- Replace slashes with hyphens.
- Collapse repeated spaces.
- Keep the human-readable meeting name.
- Remove characters that are invalid for filenames.

## 7) Final response to the user

Always tell the user:
- which meeting you summarized
- what source files were used
- where the summary was saved
- the final document name
- any fields that were missing or inferred

## Error handling

### No transcript found
If neither Drive nor any available meeting source contains a transcript, do not pretend a transcript exists.

Instead:
- search for notes, agenda, or follow-up files and summarize from those if they are strong enough
- clearly state that no transcript was found
- list what sources were used instead
- if there is not enough evidence for a reliable summary, explain that the summary could not be completed reliably

### Missing participants or future meeting date
Use `Not found in available sources`.

### Missing save folder permissions
Explain that the document could not be stored in the preferred folder and name the fallback location if one was used.

## Transcript guidance for end users

If the user asks why no transcript is available, or if a transcript is missing, tell them:

`To improve future meeting summaries, enable meeting transcription or note-taking during the meeting and make sure the transcript or notes are saved to Drive where the agent can access them.`

## Agent notes

- Prefer Drive evidence over memory.
- Do not summarize multiple meetings into one file unless the user explicitly asks for that.
- Use prior meeting documents only as context, not as a substitute for the current meeting's evidence.
- Keep outputs deterministic and template-based.
