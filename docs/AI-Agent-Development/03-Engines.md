# ADK Runtime & Event Loop

The ADK **Runtime** is the underlying engine that powers the agent application. It takes your defined components (Agents, Tools, Services) and orchestrates their execution in response to user input.

## The Event Loop

At its core, the ADK Runtime operates on an **Event Loop**. This loop facilitates communication between the *Runner* component and your *Execution Logic* (Agents, LLMs, Callbacks).

![Event Reference Diagram](/docs/images/image.png)

### Execution Flow:

1. **Trigger**: The Runner receives a user query and starts the primary Agent.
2. **Execute & Yield**: The Agent runs until it needs to report a state change, use a tool, or return a final response. It then *yields* an Event (e.g., `adk_request_credential`).
3. **Process**: The Runner intercepts the Event, updates context (like Session state), and forwards it to the client/UI.
4. **Resume**: The Agent's logic pauses while the event is handled. Once the client responds, the Runner resumes the Agent with the new context.
5. **Loop**: This cycle repeats until the agent fulfills the user query.

This event-driven architecture allows ADK to be highly extensible—enabling asynchronous UI updates, streaming text, and interrupting flows for secure credentials (like OAuth).

---

## Available Engines (Apps)

To execute an agent through the Runtime, ADK wraps the agent in an "App" engine depending on the deployment target:

| Engine | Primary Use Case |
| :--- | :--- |
| `HttpApp` | Deploys the agent as a local FastAPI web server (REST endpoints & SSE Streaming). Ideal for custom microservices. |
| `ConsoleApp` | Runs the agent interactively in a terminal command line interface. Ideal for quick debugging and local iterations. |
| `AdkApp` | Native integration wrapper designed exclusively for deploying to **Vertex AI Agent Engine**. |
| `GradioApp` | Generates a quick, locally-hosted web UI using Gradio to visually test the agent's behavior. |

---

## References

For detailed usage, configuration, and constraints, refer to the official documentation:

* **[Apps: Workflow Management Class (Engines)](https://google.github.io/adk-docs/apps/)**
* **[Agent Runtime (Executing Apps)](https://google.github.io/adk-docs/runtime/)**