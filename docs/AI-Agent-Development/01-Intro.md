# Agent Development Kit (ADK) Overview

The [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) is a modular framework for building AI agents optimized for the Google Cloud ecosystem. While compatible with frameworks like LangChain, ADK provides native integrations for Gemini and Vertex AI.

## Core Agents

An **Agent** is an autonomous execution unit that performs tasks, uses tools, and interacts with users. Extend the `BaseAgent` class into one of three primary categories:

| Agent Type | Core Engine | Primary Use Case |
| :--- | :--- | :--- |
| **[LLM Agent](https://google.github.io/adk-docs/agents/llm-agents/)** (`Agent`) | Gemini / LLMs | Natural language reasoning, dynamic decision making, and tool orchestration. |
| **[Workflow Agent](https://google.github.io/adk-docs/agents/workflow-agents/)** (`SequentialAgent`) | Predefined Logic | Deterministic execution flows (Sequence, Parallel, Loop) without LLM overhead. |
| **[Custom Agent](https://google.github.io/adk-docs/agents/custom-agents/)** (`BaseAgent`) | Custom Code | Highly tailored logic and specialized system integrations. |

## Extending Capabilities

Agents scale in functionality through modular ADK components:

* **[Models](https://google.github.io/adk-docs/agents/models/)**: Plug-and-play access to Gemini and other LLM providers.
* **[Tools & Integrations](https://google.github.io/adk-docs/integrations/)**: Equip agents with [Pre-built](https://google.github.io/adk-docs/integrations/) or [Custom](https://google.github.io/adk-docs/tools-custom/) tools (like MCP Servers) to interact with external APIs and databases.
* **[Artifacts](https://google.github.io/adk-docs/artifacts/)**: Persist generated files, code, and documents beyond the conversation lifecycle.
* **[Plugins](https://google.github.io/adk-docs/plugins/) & [Skills](https://google.github.io/adk-docs/skills/)**: Package complex behaviors and third-party services directly into agent workflows.
* **[Callbacks](https://google.github.io/adk-docs/callbacks/)**: Hook into execution lifecycles for logging, monitoring, and debugging.