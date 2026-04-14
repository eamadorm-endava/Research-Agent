# AI Agents in Gemini Enterprise

This repository is planned to be an accelerator for implementing Gemini Enterprise in any company; allowing to integrate AI Agents capable of reading/writing data from multiple sources (based on user's permissions), such as:

- Google Drive
- Google Cloud Storage
- BigQuery
- Google Calendar

leveraging full AI Agent's capabilities to solve different use cases within a company.

## System Architecture

This project is divided into three main systems:

- Data Pipelines
- MCP Servers
- AI Agents

### Data Pipelines

Data is always in very different formats and sources, this system allows to process it and make it available to the AI Agents based on the different types of authorization.

### MCP Servers

This are the way AI Agents can access the data processed by the Data Pipelines. Due to some Gemini Enterprise pre-built connectors has limited capabilities (read-only tools), it was decided to implement custom MCP Servers for the different data sources, allowing to create, read, and update data (based on user's permissions).

### AI Agents

AI Agents are the core of the system, allowing to address different use cases within a company taking advantage of Gemini Enterprise and the custom MCP servers. So that people within the company can not only interact with the data in a more natural and efficient way, but also automate tasks and processes.

### High-Level Architecture

```mermaid
graph TD
    subgraph Entry ["Access Interface"]
        User(["<b>User Query</b><br/>(Gemini Enterprise)"])
    end

    subgraph Core ["Agent Logic"]
        Agent["<b>AI Agent</b><br/>(ADK Agent Engine)"]
    end

    subgraph Gateway ["Protocol Layer (MCP)"]
        BQ_MCP["<b>BQ MCP Server</b>"]
        GCS_MCP["<b>GCS MCP Server</b>"]
        Drive_MCP["<b>Drive MCP Server</b>"]
        Calendar_MCP["<b>Calendar MCP Server</b>"]
    end

    subgraph Service ["GCP API Resources"]
        BQ_Res[("<b>BigQuery</b><br/>Datasets/Tables")]
        GCS_Res[("<b>Cloud Storage</b><br/>Buckets/Blobs")]
        Drive_Res[("<b>Google Drive</b><br/>Docs/Folders")]
        Calendar_Res[("<b>Google Calendar</b><br/>Events")]
    end

    subgraph Processing ["Data Pipelines"]
        BQ_Pipe["<b>BQ Ingestion Pipeline</b>"]
        GCS_Pipe["<b>GCS Ingestion Pipeline</b>"]
        Drive_Pipe["<b>Drive Ingestion Pipeline</b>"]
    end

    %% Flow through MCP
    User --> Agent
    Agent --> BQ_MCP
    Agent --> GCS_MCP
    Agent --> Drive_MCP
    Agent --> Calendar_MCP

    BQ_MCP <--> BQ_Res
    GCS_MCP <--> GCS_Res
    Drive_MCP <--> Drive_Res
    Calendar_MCP <--> Calendar_Res

    %% Ingestion Flow (visually below Databases)
    BQ_Res <--- BQ_Pipe
    GCS_Res <--- GCS_Pipe
    Drive_Res <--- Drive_Pipe
```

## Project Structure

```text
Research-Agent/
├── agent/                      # ADK Agent implementation
│   ├── core_agent/            # Agent package (entry point + internal modules)
│   │   ├── agent.py           # Application entry point (wires config → builder → agent)
│   │   ├── config/            # Pydantic Settings (centralized env var validation)
│   │   ├── builder/           # Builder pattern (AgentBuilder, MCPToolsetBuilder, skills)
│   │   └── security/          # Token utilities (ID tokens, delegated OAuth)
│   ├── skills/                # ADK Skills (meeting-summary, etc.)
│   ├── deployment/            # Vertex AI / Agent Engine deployment scripts
│   └── tests/                 # Agent unit and integration tests
├── mcp_servers/               # MCP server implementations
│   ├── big_query/             # BigQuery MCP server
│   ├── gcs/                   # Cloud Storage MCP server
│   ├── google_drive/          # Google Drive MCP server
│   └── google_calendar/       # Google Calendar & Meet MCP server
├── terraform/                 # Infrastructure as Code
│   ├── ai_agent_resources/    # Service accounts, IAM, and APIs
│   ├── bq_mcp_server_resources/
│   ├── gcs_mcp_server_resources/
│   ├── shared_resources/      # Shared state and Artifact Registry
│   └── scripts/               # Bootstrap and trigger scripts
├── docs/                      # Detailed documentation
├── notebooks/                 # Exploration and research notebooks
├── Makefile                   # Development automation commands
├── pyproject.toml             # Python project configuration (uv)
```

## Getting Started

### Developing with Dev Containers

We recommend using **VS Code Dev Containers** for an optimal development experience.

*   **Consistency**: Ensures everyone uses the exact same toolset and OS versions.
*   **Zero Setup**: All dependencies (uv, gcloud, terraform, docker) come pre-installed.
*   **Isolation**: Keep your local machine clean; everything runs inside a Docker container.

To use Dev Containers, the only requirements are to have **Docker** installed and the **Dev Containers extension** (available for both **VS Code** and **Antigravity**).

To start, simply open this project and click **"Reopen in Container"** when prompted.

---

### Prerequisites (If not using Dev Containers)

Ensure you have the following tools installed:

- **uv**: Python package and project manager.
- **make**: Task runner for development commands.
- **gcloud CLI**: For Google Cloud Platform interactions.
- **Terraform**: For infrastructure deployment and management.
- **Docker**: Required for building and testing MCP server images.

### Local Development & Testing

Use the `Makefile` commands to manage common tasks:

#### 1. Setup & Environment
```bash
# Authenticate with Google Cloud
make gcloud-auth

# Install dependencies using uv
uv sync --all-groups
```

#### 2. Running Tests
```bash
# Run the core Agent unit tests
make test-agent

# Run MCP Server integration tests
make run-bq-tests
make run-gcs-tests
make run-drive-tests
```

#### 3. Execution & Local Verification
```bash
# Start the Agent Web UI (ADK)
make run-ui-agent

# Start MCP Servers locally for direct testing
make run-bq-mcp-locally
make run-gcs-mcp-locally
make run-drive-mcp-locally
make run-calendar-mcp-locally
```

## Documentation

For more detailed information about each component, refer to the following documentation:

### Core AI Agent
- [Agent Overview](agent/core_agent/README.md): Architecture, builder pattern, configuration, and deployment.
- [Builder Module](agent/core_agent/builder/README.md): How `AgentBuilder`, `MCPToolsetBuilder`, and `get_skill_toolset` work.

### MCP Servers
- [BigQuery MCP Server](mcp_servers/big_query/README.md): BigQuery connector implementation.
- [Cloud Storage (GCS) MCP Server](mcp_servers/gcs/README.md): GCS connector implementation.
- [Google Drive MCP Server](mcp_servers/google_drive/README.md): Google Drive connector implementation.
- [Google Calendar MCP Server](mcp_servers/google_calendar/README.md): Google Calendar & Meet connector implementation.

### Security & Authentication
- [Authentication Methods](docs/Authentication/README.md): Strategies for identity propagation (DWD vs. OAuth).

### ADK Framework
- [ADK Introduction](docs/ADK/ADK-01-Intro.md): Introduction to the Agent Development Kit.
- [AI Agent Development Guide](docs/AI-Agent-Development/README.md): Step-by-step guide for building, deploying, and connecting agents.
