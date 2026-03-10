# Conversational Context: Session, State, and Memory

## Session: The Current Conversation

Represents a single, ongoing conversation/interaction between the user and the agent.

Contains the chronological sequence of messages and actions taken by the agent (referred to as *Events*) during that specific interaction.

A *Session* can also hold temporal data (*State*) relevant only during the conversation.

When a user starts a new conversation, the *SessionService* creates a new *Session* object (google.adk.sessions.Session). This object acts as a container for the conversation and holds everything related to it. 

### Session Object Properties


- `id`: A unique identifier for the session. A *SessionService* object can handle multiple *Session* objects, each with its own unique ID.
- `app_name`: Identifies which agent application this conversation belongs to.
- `user_id`: Identifies the user associated with the session (conversation).
- `events`: A chronologcal sequence of all interactions (*Event* objects - user messages, agent responses, tool actions) that have occurred in the conversation.
- `state`: A place to store temporary data relevant only to this specific, ongoing conversation.
- last_update_time`: The timestamp of the last update to the session.

## State (session.state): Data Within the Conversation

Data stored within a specific *Session*.

Used to manage information relevant only to the current, active conversation thread (e.g. items in a shopping cart during this chat, user preferences for the current session, etc.).

Check more info about the *State* [here](https://google.github.io/adk-docs/sessions/session/).

## Memory: Searchable, Cross-Session Information

Represents a store of information that might span multiple past sessions or include external data sources.

It acts as a knowledge base the agent can search to recall information or context beyond the immediate conversation.

# Managing Context: Services

ADK provides services to manage these concepts:

## SessionService

Manages the different conversation threads (*Session* objects).

- Handles the lifecycle: creating, retrieving, updating (appending *Events*, modifying *State*), and deleting individual *Session*s.

This *SessionService* object is typically used instead of directly manipulating *Session* objects.

### SessionService Implementations

#### **InMemorySessionService** (google.adk.sessions.InMemorySessionService)

- **How it works**: Stores all session data directly in the application's memory.
- **Persistence**: None. Data is lost when the application restarts.
- **Requires**: Nothing extra.
- **Best for**: Quick development, local testing, examples, and scenarios where long-term presistence isn't required. This is the default implementation when no other is specified.

#### **VertexAiSessionService** (google.adk.sessions.VertexAiSessionService)

- **How it works**: Stores all session data in a Vertex AI session using API calls.
- **Persistence**: Yes. Data is managed reliably and scalably via [Vertex AI Agent Engine](https://google.github.io/adk-docs/deploy/agent-engine/).
- **Requires**:
    - A GCP Project (uv add vertexai)
    - A GCS Bucket 
        - Grant Storage Object User access - To read and write pipeline artifacts in the the bucket
    - A Reasoning Engine resource name/ID. See the [tutorial](https://google.github.io/adk-docs/deploy/agent-engine/)
- **Best for**: Scalable production applications deployed on Google Cloud, especially when integrating with other Vertex AI features.

#### **DatabaseSessionService** (google.adk.sessions.DatabaseSessionService)

- **How it works**: Connects to a relational database (e.g., PostgreSQL, MySQL, SQLite) to store session data persistently in tables.
- **Persistence**: Yes. Data survives application restarts.
- **Requires**:
    - A configured database.
    - An Async database driver (e.g., sqlite+aiosqlite)
- **Best for**: Applications needing reliable, persistent storage that you manage yourself.

## MemoryService

Manages the Long-Term Knowledge Store (*Memory*)

- Handles ingesting information (ofthen from completed *Sessions*) into the long-term store.

- Provides methods to search this stored knowledge based on queries.

**Implementations**: ADK offers different implementations for both *SessionService* and *MemoryService*, allowing you to choose the storage backend that best fits your application's needs.

Notably, **in-memory implementations** are provided for both services; these are designed specifically for local testing and fast development. It's important to remember that all data stored using these in-memory options (*sessions*, *state*, or *long-term knowledge*) is lost when you application restarts. For persistance and scalability beyond local testing, ADK also offers cloud-based and database service options. 


**Information copied from [ADK-Conversational Context](https://google.github.io/adk-docs/sessions/), [ADK-Session](https://google.github.io/adk-docs/sessions/session/)