# Build Agents with the [Agent Development Kit](https://google.github.io/adk-docs/)

Agent Development Kit (ADK) is a flexible and modular framework for developing and deploying AI agents optimized for Gemini and Googe ecosystem.

It is compatible with other frameworks such as LangChain and LangGraph. Nevertheless, if other framework needs to be used, it is required to develop a [custom agent](https://docs.cloud.google.com/agent-builder/agent-engine/develop/custom).

## Agents

In ADK, an **Agent** is a self-contained execution unit designed to act autonomously to achieve specific goals. Agents can perform tasks, interact with users, utilize external tools, and coordinate with other agents.

To create functional agents, it is required to extend the *BaseAgent* class in one of the three main ways:

### Core Agent Categories

#### LLM Agents (*LLMAgent*, *Agent*):
 These agents utilize Large Language Models (LLMs) as their core engine to understand natural language, reason, plan, generate responses, and dynamically decide how to proceed or which tools to use, making them ideal for flexible, language-centric tasks.

See more [here](https://google.github.io/adk-docs/agents/llm-agents/)

#### Workflow Agents (*SequentialAgent*, *ParallelAgent*, *LoopAgent*): 

These specialized agents control the execution flow of other agents in predefined, deterministic patterns (sequence, parallel, or loop), without using an LLM for the flow control itself, perfect for structured processes needing predictable execution.

See more [here](https://google.github.io/adk-docs/agents/workflow-agents/)

#### Custom Agents:

Created by extending BaseAgent directly, these agents allow you to implement unique operational logic, specific control flows, or specialized integrations not covered by the standard types, catering to highly tailored application requirements.

See more [here](https://google.github.io/adk-docs/agents/custom-agents/)


### Choosing the Right Agent Type

| **Feature** | **LLM Agent** | **Workflow Agent** | **Custom Agent** |
|:--:|--:|--:|--:|
| **Primary Function**| Reasoning, Generation, Tool Use | Controling Agent Execution Flow | Implementing Unique Logic/Integrations |
| **Core Engine** | Large Language Model (LLM)| Predefined Logic (Sequence, Parallel, Loop)| Custom Code |
| **Determinism** | Non-deterministic (Flexible)| Deterministic (Predictable) | Can be either, based on implementation |
| **Primary Use**| Language tasks, Dynamic Decisions | Structured processes, Orchestration | Tailored  requirements, Specific workflows |

### Extend Agent Capabilities

ADK allows to significantly expand what an agent can do through several key mechanisms:

#### [AI Models](https://google.github.io/adk-docs/agents/models/)

Integration with Gemini models and other providers.

#### [Artifacts](https://google.github.io/adk-docs/artifacts/)

Enable agents to create and manage persistent outputs like:

- Files
- Code
- Documents

That exist beyond the conversation lifecycle

#### [Pre-built tools and integrations](https://google.github.io/adk-docs/integrations/)

Equip an agent with a wide array tools, plugins, and other integrations to interact with the world, including web sites, MCP tools, applications, databases, programming interfaces, and more.

#### [Custom tools](https://google.github.io/adk-docs/tools-custom/)

Create your own, task-specific tools for solving specific problems with precision and control.

#### [Plugins](https://google.github.io/adk-docs/plugins/)

Integrate complex, pre-packaged behaviours and third-party services directly into your agent's workflow.

#### [Skills](https://google.github.io/adk-docs/skills/)

Use prebuilt or custom Agent Skills to extend agent capabilities in a way that works efficiently inside AI context window limits.

#### [Callbacks](https://google.github.io/adk-docs/callbacks/)

Hook into specific events during an agent's execution lifecycle to add logging, monitoring, or custom side-effects without altering core agent logic.