# AI Agent Development Documentation

This directory contains guides and reference materials for developing, deploying, and connecting AI Agents using the Agent Development Kit (ADK) and Gemini Enterprise.

## Reading Order

We recommend reviewing these documents logically as they walk through building, hosting, and connecting an agent:

1. **[01-Intro.md](01-Intro.md)**: Introduction to the Agent architecture and framework.
2. **[02-Conversational-Context.md](02-Conversational-Context.md)**: Managing state and context in multi-turn conversations.
3. **[03-Engines.md](03-Engines.md)**: Overview of underlying Reasoning Engines and model configurations.
4. **[04-Agent-Engine-Deployment.md](04-Agent-Engine-Deployment.md)**: Guide to building, testing, and deploying the Agent Engine.
5. **[05-Gemini-Enterprise-Connection.md](05-Gemini-Enterprise-Connection.md)**: Connecting the deployed agent to Gemini Enterprise.
6. **[06-OAuth-Inside-Gemini-Enterprise.md](06-OAuth-Inside-Gemini-Enterprise.md)**: Detailed 5-step flow for secure OAuth integration in Gemini Enterprise.
7. **[07-Storage-and-Ingestion-Architecture.md](07-Storage-and-Ingestion-Architecture.md)**: End-to-end management of session artifacts, Multi-modal documents, Zero-Copy URIs, and identity-aware IAM security for user-uploaded files.
8. **[08-KB-Ingestion-Pipeline.md](08-KB-Ingestion-Pipeline.md)**: KB ingestion module: tools for triggering and monitoring EKB pipeline runs.
9. **[09-Multi-Agent-Architecture.md](09-Multi-Agent-Architecture.md)**: Coordinator → Specialist multi-agent topology: rationale, delegation patterns, and OAuth.

## Reference

- **[10-AgentTool-vs-SubAgents.md](10-AgentTool-vs-SubAgents.md)**: Deep-dive comparison of the two ADK multi-agent delegation patterns — `AgentTool` (explicit tool invocation) vs. `sub_agents=` (LLM-transfer) — covering internal mechanics, event propagation, and a decision guide.
