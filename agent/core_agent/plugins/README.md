# ADK Plugins

Plugins provide a powerful way to bundle multi-hook logic, tools, and state management into a single modular component.

## Plugins vs. Callbacks
- A **Callback** is typically a single function targeting one specific lifecycle hook (e.g., `before_agent`).
- A **Plugin** is a class that can hook into multiple lifecycle events simultaneously, register its own tools, and maintain internal state across hooks. 

## Plugin Lifecycle Hooks
Plugins have access to all the standard ADK callbacks (`before_agent`, `after_model`, etc.), but they also expose specialized messaging hooks:
- **`on_user_message`**: Triggers when a new user message arrives but before it is processed.
- **`on_model_message`**: Triggers when the model is generating a message.

## When to use a Plugin
Use a plugin when you need cohesive, reusable logic that spans multiple hooks, such as intercepting user attachments (`on_user_message`) and later validating the model's response (`after_model`) within the same domain.
