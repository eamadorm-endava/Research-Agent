# Time Tools Module

The `time_tools` module provides native tools for the AI agent to retrieve current date and time information. This ensures the agent has a reliable way to orient itself in time without relying on potentially stale information from the system prompt.

## Tools

### `get_current_time`

Returns the current date and time in ISO 8601 format for the Central Time zone (`America/Chicago`).

#### Technical Implementation
- **Class**: `GetCurrentTimeTool`
- **File**: `agent/core_agent/tools/time_tools.py`
- **Timezone**: Central Time (CST/CDT) using `zoneinfo`.
- **Format**: ISO 8601 (e.g., `2026-05-06T00:12:50-05:00`).

#### Response Schema (`GetCurrentTimeResponse`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `current_time` | `str` | The current time in ISO 8601 format. |
| `timezone` | `str` | The timezone used (`America/Chicago`). |
| `execution_status` | `str` | "success" or "error". |

## Usage in Agent
The tool is registered in `agent/core_agent/agent.py` as a native tool:

```python
from .tools.time_tools import GetCurrentTimeTool

root_agent = (
    AgentBuilder(...)
    .with_native_tools([
        ...,
        GetCurrentTimeTool(),
    ])
    .build()
)
```

## Testing
Unit tests are located in `agent/tests/test_time_tools.py`. They verify:
1. Happy path: Valid ISO string returned with correct timezone offset.
2. Tool declaration: Correct naming and description for Gemini.
