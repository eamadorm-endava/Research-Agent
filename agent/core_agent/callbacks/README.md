# Agent Callbacks

This module contains functional hooks that integrate with the ADK Agent lifecycle events.

## Callbacks Overview

### `artifact_rendering.py`
- **`render_pending_artifacts`**: A post-turn `after_agent_callback` that resolves and renders queued artifacts (local or GCS) as inline `types.Part` objects for the Gemini Enterprise UI.

### `ingestion_status.py`
- **`sync_ingestion_status`**: A `before_agent_callback` registered on the **Coordinator** agent. On every turn it reads the `pending_ingestions` list from session state, polls the EKB pipeline's `/status/{job_id}` endpoint for each pending job, and—when a job finishes—injects a `[SYSTEM UPDATE]` event into the session history so Gemini Enterprise surfaces a proactive notification to the user. Jobs that finish are removed from the pending list; jobs that are still running or encounter transient errors remain queued.

## Registration

```python
# after_agent_callback — registered via AgentBuilder.build()
Agent(..., after_agent_callback=render_pending_artifacts)

# before_agent_callback — registered via AgentBuilder.with_before_agent_callback()
AgentBuilder(...).with_before_agent_callback(sync_ingestion_status).build()
```
