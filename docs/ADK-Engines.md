# Agent Runtime

The ADK *Runtime* is the underlying engine that powers the agent application during user interactions. It's the system that takes the defined agents, tools, and callbacks and orchestrates their execution in response to user input, managing the flow of information, state changes, and interactions with external services like LLMs or storage.

Think of the *Runtime* as the ***engine*** of the agentic application. You define the parts (agent, tools, SessionService, MemoryService), and the *RunTime* handles how they connect and run together to fulfill a user's request.

## The Event Loop

In its core, the ADK Runtime operates on an Event Loop. This loop facilitates a back-and-forth communication between the *Runner* component and your defined "Execution Logic" (including the Agents, the LLM calls they make, Callbacks, and Tools).

![alt text](/docs/images/image.png)

In simple terms:

1. The *Runner* receives a user query and asks the main Agent to start processing.

2. The Agent (and its associated logic) runs until it has something to report (like a response, a request to use a tool, or a state change) – it then yields or emits an Event.

3. The Runner receives this Event, processes any associated actions (like saving state changes via Services), and forwards the event onwards (e.g., to the user interface).

4. The Agent's logic resumes from where it paused only after the Runner has processed the event, and then potentially sees the effects of the changes committed by the Runner.
5. This cycle repeats until the agent has no more events to yield for the current user query.

This event-driven loop is the fundamental pattern governing how ADK executes your agent code.