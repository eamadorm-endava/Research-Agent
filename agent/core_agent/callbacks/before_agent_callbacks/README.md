# Before Agent Callbacks

This directory contains callbacks that hook into the `before_agent` ADK lifecycle event. 

These callbacks run synchronously or asynchronously right when the agent's turn begins, before any LLM execution occurs. Use these callbacks to fetch initial context, sync state with external APIs, or validate the invocation context.
