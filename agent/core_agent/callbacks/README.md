# Agent Callbacks

This module contains functional hooks that integrate with the ADK Agent lifecycle events.

## Callbacks Overview

### `file_ingestion.py`
- **`FileIngestionToolWrapper`**: A tool wrapper that intercepts backend MCP servers generating files mid-turn and injects the zero-copy URI directly into the conversation history.
- **`FileIngestionToolsetWrapper`**: A convenience wrapper for `BaseToolset` that automatically applies the `FileIngestionToolWrapper` to all tools within the toolset.

### `ingestion_status.py`
- **`sync_ingestion_status`**: A `before_agent_callback` registered on the **Coordinator** agent. On every turn it reads the `pending_ingestions` list from session state, polls the EKB pipeline's `/status/{job_id}` endpoint for each pending job, and—when a job finishes—injects a `[SYSTEM UPDATE]` event into the session history so Gemini Enterprise surfaces a proactive notification to the user. Jobs that finish are removed from the pending list; jobs that are still running or encounter transient errors remain queued.

## Registration Examples

The hooks in this module are applied at different stages of the agent's construction.

```python
# 1. Agent Callbacks (e.g. sync_ingestion_status)
# Registered explicitly at the agent level to intercept turn cycles.
AgentBuilder(name="Coordinator") \
    .with_before_agent_callback(sync_ingestion_status) \
    .build()
```

# 2. Tool Wrappers (e.g. FileIngestion)
These are applied AUTOMATICALLY by the AgentBuilder during construction.
Developers do NOT need to manually wrap their tools. The internal implementation 
in `AgentBuilder._consolidate_tools()` handles this transparently:

```python
def _consolidate_tools(self) -> list[Union[BaseTool, BaseToolset]]:
    total_tools = []
    for tool in self._registered_tools:
        if isinstance(tool, BaseTool):
            total_tools.append(FileIngestionToolWrapper(tool))
        elif isinstance(tool, BaseToolset):
            total_tools.append(FileIngestionToolsetWrapper(tool))
    return total_tools
```
