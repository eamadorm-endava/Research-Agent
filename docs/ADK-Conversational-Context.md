# Conversational Context: Session, State, and Memory

## Session: The Current Conversation

Represents a single, ongoing conversation/interaction between the user and the agent.

Contains the chronological sequence of messages and actions taken by the agent (referred to as *Events*) during that specific interaction.

A *Session* can also hold temporal data (*State*) relevant only during the conversation.

## State (session.state): Data Within the Conversation

Data stored within a specific *Session*.

Used to manage information relevant only to the current, active conversation thread (e.g. items in a shopping cart during this chat, user preferences for the current session, etc.).

Check more info about the *State* [here]().

## Memory: Searchable, Cross-Session Information

Represents a store of information that might span multiple past sessions or include external data sources.

It acts as a knowledge base the agent can search to recall information or context beyond the immediate conversation.

# Managing Context: Services

ADK provides services to manage these concepts:

## SessionService

Manages the different conversation threads (*Session* objects)

- Handles the lifecycle: creating, retrieving, updating (appending *Events*, modifying *State*), and deleting individual *Session*s.

## MemoryService

Manages the Long-Term Knowledge Store (*Memory*)

- Handles ingesting information (ofthen from completed *Sessions*) into the long-term store.

- Provides methods to search this stored knowledge based on queries.

**Implementations**: ADK offers different implementations for both *SessionService* and *MemoryService*, allowing you to choose the storage backend that best fits your application's needs.

Notably, **in-memory implementations** are provided for both services; these are designed specifically for local testing and fast development. It's important to remember that all data stored using these in-memory options (*sessions*, *state*, or *long-term knowledge*) is lost when you application restarts. For persistance and scalability beyond local testing, ADK also offers cloud-based and database service options. 


**Information copied from [ADK-official documentation](https://google.github.io/adk-docs/sessions/)