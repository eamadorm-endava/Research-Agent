# Sync Ingestion Status Callback

This `before_agent` callback automatically synchronizes the status of pending Enterprise Knowledge Base (EKB) ingestion jobs.

When the agent starts a turn, this callback reads the `PENDING_INGESTIONS_KEY` from the session state. For any pending jobs, it makes a live HTTP request to the EKB service to check their current status. The updated status is then injected into the agent's context, ensuring the LLM has up-to-date information before it generates a response.
