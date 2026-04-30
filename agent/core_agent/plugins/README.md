# Agent Plugins

This module contains integrated behaviors and message interceptors that extend the ADK Application logic.

## Plugins Overview

### `ingestion/`
- **`GeminiEnterpriseFileIngestionPlugin`**: Intercepts user messages to persist inline binary data to GCS and replace it with URI references. This ensures files uploaded via Gemini Enterprise are available for the agent's multi-modal analysis.

## Registration

Plugins are registered in the `App` (or `AdkApp`) via the `AppBuilder`:

```python
from .plugins.ingestion.plugin import GeminiEnterpriseFileIngestionPlugin

App(
    ...
    plugins=[GeminiEnterpriseFileIngestionPlugin()]
)
```
