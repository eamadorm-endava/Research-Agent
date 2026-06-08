# ADK Callbacks

Callbacks allows to hook into the lifecycle of an ADK Agent to execute custom logic at specific moments during a turn.

## What is a Callback?
A callback is a synchronous or asynchronous Python function that the ADK runtime triggers natively during the agent's reasoning loop. They are useful for cross-cutting concerns like logging, state synchronization, security validations, and custom interceptions that should happen transparently behind the scenes without the LLM explicitly asking for them.

## When to use a Callback
Use a callback when you need logic to run automatically:
- Before or after an agent starts reasoning.
- Before or after the LLM model is invoked.
- Before or after a tool executes.

## Types of Callbacks in ADK

The ADK exposes the following core callback hooks:
- **`before_agent`**: Runs immediately when an agent is invoked, before any LLM calls are made. Great for setting up context, validating inputs, or syncing external state.
- **`before_model`**: Runs just before the LLM is called. Useful for modifying the prompt or the system instructions dynamically.
- **`after_model`**: Runs just after the LLM responds but before the response is parsed.
- **`after_agent`**: Runs at the very end of the agent's turn, right before control is returned to the user or coordinator.
- **`before_tool`**: Runs before a specific tool executes. Useful for input validation or logging.
- **`after_tool`**: Runs after a tool executes. Useful for modifying the tool's output before the LLM sees it.

## Callback Scope & Subagents

**IMPORTANT:** Callbacks in the ADK are scoped strictly to the agent they are registered on. 
If you register a callback on a `Coordinator` (root agent), it will **only** trigger when the Coordinator takes a turn. If the Coordinator delegates a task to a `subagent`, the Coordinator's callbacks will be **paused** while the subagent runs its own internal loops.

If you have a callback that must execute continuously on every single turn (e.g., polling background jobs or syncing global state), you must register that callback explicitly on **both** the root agent and the subagents:

```python
# The callback will only run on the Coordinator's turns
root_agent = AgentBuilder().with_before_agent_callback([my_callback]).build()

# The callback will now also run on the Subagent's turns
sub_agent = AgentBuilder().with_before_agent_callback([my_callback]).build()
```

## Implemented Callbacks

Currently, this implementation specifically uses `before_agent` callbacks and **Tool Wrappers** (which hook into the tool execution cycle):

- **`before_agent_callbacks/ekb_status_sync`**: A `before_agent` callback that runs automatically when an agent is invoked. It implicitly polls the status of any pending EKB ingestion jobs stored in the ADK Session State, updating the context behind the scenes without the LLM explicitly needing to call a tool.
- **`tool_wrappers/file_ingestion_wrapper`**: A specific tool wrapper (operating similarly to an `after_tool` callback) that intercepts file paths returned by MCP servers (like Google Drive or GCS) and natively injects their contents directly into the agent's context.
