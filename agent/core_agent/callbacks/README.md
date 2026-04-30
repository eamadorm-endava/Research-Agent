# Agent Callbacks

This module contains functional hooks that integrate with the ADK Agent lifecycle events.

## Callbacks Overview

### `artifact_rendering.py`
- **`render_pending_artifacts`**: A post-turn callback that resolves and renders queued artifacts (local or GCS) as inline parts for the Gemini Enterprise UI.

## Registration

Direct agent callbacks are registered in the `Agent` via the `AgentBuilder`:

```python
from .callbacks.artifact_rendering import render_pending_artifacts

Agent(
    ...
    after_agent_callback=render_pending_artifacts
)
```
