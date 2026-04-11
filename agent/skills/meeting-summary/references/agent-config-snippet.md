# Agent configuration snippet

Use this trigger guidance in the agent instructions or tool-routing prompt.

## Trigger text

Use the `meeting-summary` skill when the user asks for a summary of one specific meeting and the request implies creating or saving a meeting recap document.

Examples:
- summarize the Acme weekly sync from March 14
- create a meeting summary for yesterday's client call
- generate and save a summary for the QBR meeting with Contoso
- get me the summary of the pricing follow-up meeting

When triggered, the agent should:
1. use MCP Drive Server to search for the matching meeting transcript, notes, agenda, and related documents
2. extract the meeting date, name, participants, main purpose, conclusions, next steps, future session date, and useful related documents
3. for follow-up meetings, search Drive for earlier related summaries or supporting documents to recover context when needed
4. generate a document summary from the skill template in `assets/meeting-summary-template.md`
5. save the file into the user's Drive folder `AI Meetings Summaries`, creating the folder if needed
6. tell the user which meeting was summarized, what files were used, where the document was saved, and whether any required fields were missing
7. if no transcript is available, fall back to strong notes if possible and tell the user how to enable transcripts for future meetings

## Short version

Trigger `meeting-summary` for requests to summarize a specific meeting into a standardized document saved to the user's Drive.
