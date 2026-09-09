# Continuation Plugin

## Overview
The `ContinuationPlugin` is a resilience component that detects silent model failures caused by LLM payload/context overload and gracefully prompts the user to continue the interaction.

---

## The Problem It Solves
When interacting with complex reasoning models or large context windows, the Gemini model can occasionally exhaust token budgets, hit internal generation thresholds, or experience payload truncation. When this happens:
- The LLM returns an empty payload (no text parts and no function calls).
- The user experiences a "silent failure" where the agent appears to hang or return nothing.

Without this plugin, empty responses pass through to the frontend, degrading user experience.

---

## What This Plugin Does
The plugin intercepts the model response in `after_model_callback`:
1. **Payload Inspection**: Checks if the response contains any text parts or function call executions.
2. **Silent Failure Detection**: If neither text nor tool calls are present, it flags an empty payload.
3. **Graceful Fallback Injection**: Dynamically constructs and injects a user-friendly guidance message:
   > *"I was unable to complete the request in a single pass. Please write **'continue'** to complete the tasks."*

---

## How to Use It

### Registration
Register the `ContinuationPlugin` inside the multi-agent application builder (`agent/core_agent/agent.py`):

```python
from agent.core_agent.plugins.continuation import ContinuationPlugin
from agent.core_agent.builder import AppBuilder

app = (
    AppBuilder(
        agent=root_agent,
        gcp_config=GCP_CONFIG,
        agent_config=COORDINATOR_CONFIG,
    )
    .with_plugins([
        ContinuationPlugin(),
        # other plugins...
    ])
    .build()
)
```

### Lifecycle Hook
- **`after_model_callback(callback_context, llm_response)`**: Examines `llm_response.content.parts` and `llm_response.get_function_calls()`. Modifies the response in-place if an empty payload is detected.
