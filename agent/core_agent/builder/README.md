# Builder Module

The `builder/` package implements the **Builder Pattern** to construct the ADK Agent and its tool dependencies. It separates the _what_ (configuration) from the _how_ (construction logic), enabling clean, testable, and environment-agnostic agent assembly.

## Module Structure

```
builder/
├── __init__.py          # Public API: AgentBuilder, MCPToolsetBuilder, get_skill_toolset
├── agent_builder.py     # Fluent orchestrator for the full agent
├── mcp_factory.py       # Factory for MCP toolsets (auth + connection)
└── skills_factory.py    # Loader for ADK skills from disk
```

## Components

### `AgentBuilder` — Fluent Orchestrator

The central entry point for agent construction. It accepts configuration objects, manages internal builders, and exposes a **fluent API**:

```python
root_agent = (
    AgentBuilder(
        agent_config=COORDINATOR_CONFIG,
        gcp_config=GCP_CONFIG,
        auth_config=GOOGLE_AUTH_CONFIG,
    )
    .with_subagents([research_agent, ingestion_agent])
    .with_before_agent_callback(sync_ingestion_status)
    .with_native_tools([GetArtifactUriTool(), load_artifacts])
    .build()
)
```

**Responsibilities:**
- Initializes the VertexAI client with GCP project and region
- Creates an internal `MCPToolsetBuilder` for MCP server construction
- Accumulates tools (MCP toolsets, skill toolsets, native tools, sub-agents) via fluent method calls
- Assembles the final `Agent` with model, planner, instructions, tools, callbacks, and output key

**Fluent methods:**
| Method | Purpose |
|---|---|
| `with_skills(names)` | Loads ADK skills from `agent/skills/` and registers them |
| `with_mcp_servers(configs)` | Builds and registers `McpToolset` instances |
| `with_native_tools(tools)` | Registers `BaseTool` instances or plain callables (auto-wrapped in `FunctionTool`) |
| `with_subagents(agents)` | Registers specialist agents for LLM-transfer delegation via `sub_agents=` |
| `with_output_key(key)` | Persists the agent's final text response to session state under the given key |
| `with_before_agent_callback(fn)` | Sets the `before_agent_callback` executed before each agent turn |
| `build(enable_artifact_rendering)` | Assembles and returns the `Agent`; when `True` (default), registers `render_pending_artifacts` as `after_agent_callback` |

---

### `MCPToolsetBuilder` — MCP Factory

Constructs `McpToolset` instances configured for the correct execution environment. This builder **strictly separates** two authentication modes:

| Environment | OAuth Flow | Headers |
|---|---|---|
| **Local** | ADK-managed OAuth (scheme + credentials) | `X-Serverless-Authorization` (ID token) |
| **Production** | Gemini Enterprise-managed OAuth | `X-Serverless-Authorization` + `Authorization` (delegated token) |

**Key methods:**

| Method | Visibility | Purpose |
|---|---|---|
| `build()` | Public | Assembles the complete `McpToolset` |
| `_get_local_auth_params()` | Private | Builds ADK OAuth scheme for local dev |
| `_get_header_provider_function()` | Private | Creates a closure that generates runtime headers |

**Header Provider Pattern:** The `_get_header_provider_function` returns a **closure** that captures builder-time configuration (`mcp_config`, `prod_execution`) and evaluates security tokens at runtime when ADK invokes each tool call.

---

### `get_skill_toolset()` — Skill Loader

A standalone factory function that dynamically loads ADK skills from the `agent/skills/` directory:

```python
toolset = get_skill_toolset("meeting-summary")
# Loads from agent/skills/meeting-summary/
```

**Behavior:**
- Resolves the skill directory path relative to the builder module
- Validates that the directory exists before loading
- Raises `FileNotFoundError` with a clear message if the skill is missing
- Returns a `SkillToolset` wrapping the loaded skill

## Adding a New Tool

### New MCP Server

1. Create a config class in `config/mcp_settings.py` inheriting from `BaseMCPConfig`
2. Instantiate a singleton in the same file (e.g., `NEW_MCP_CONFIG = NewMCPConfig()`)
3. Export it from `config/__init__.py`
4. Add the singleton to `mcp_servers_to_mount` in `agent.py`

### New Skill

1. Create a new skill directory under `agent/skills/<skill-name>/`
2. Add the required `SKILL.md` file with instructions
3. Add the skill name to `skills_to_mount` in `agent.py`
