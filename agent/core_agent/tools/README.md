# Agent Tools

This module contains standalone ADK tools that are explicitly registered with the Agent to provide specific capabilities.

## Tools Overview

### `artifact_tools.py`
- **`GetArtifactUriTool`**: Retrieves the canonical GCS URI for a file registered in the current session.
- **`ImportGcsToArtifactTool`**: Registers an external GCS object as an ADK session artifact for zero-copy analysis.

## Registration

These tools are registered in the `Agent` via the `AgentBuilder`:

```python
from .tools.artifact_tools import GetArtifactUriTool, ImportGcsToArtifactTool

agent_builder.with_native_tools([
    GetArtifactUriTool(),
    ImportGcsToArtifactTool()
])
```
