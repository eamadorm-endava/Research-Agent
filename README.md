# Research-Agent

An AI-powered research platform combining the Agent Development Kit (ADK) with Google Cloud integrations exposed through Model Context Protocol (MCP) servers.

## Overview

This repository contains two main areas:

### 1. Agent Development using ADK
Build and customize intelligent agents using the Agent Development Kit. The agent can connect to MCP servers for Google Cloud capabilities without hardcoding tool definitions in the agent itself.

### 2. MCP Servers for GCP Services
Independent MCP servers connect the agent to Google Cloud Platform services, including:
- **BigQuery** - Query and analyze large datasets
- **Cloud Storage (GCS)** - Manage buckets and objects

**Key differentiator:** these MCP servers support write operations in addition to read operations, enabling agents to create, update, and modify data in supported services.

## Project Structure

```
Research-Agent/
├── agent/                      # Agent Development Kit (ADK) implementation
│   ├── core_agent/            # Core agent components and logic
│   │   ├── agent.py           # Main agent implementation
│   │   ├── config.py          # Agent configuration
│   │   └── model_armor.py     # Model safeguards and alignment
│   └── __init__.py
│
├── mcp_servers/               # MCP server implementations
│   ├── big_query/             # BigQuery MCP server
│   └── gcs/                   # Cloud Storage MCP server
│
├── terraform/                  # Infrastructure as Code
│   ├── ai_agent_resources/    # Agent service accounts and APIs
│   ├── bq_mcp_server_resources/
│   ├── gcs_mcp_server_resources/
│   ├── shared_resources/      # Shared Artifact Registry ownership
│   └── scripts/               # Bootstrap and trigger setup scripts
│
├── docs/                       # Detailed documentation
│   │                           # In-depth explanations for complex topics
│   └── ADK-Intro.md
│
├── notebooks/                  # Jupyter notebooks for exploration
│   └── model_armor.ipynb
│
├── pyproject.toml             # Python project configuration
├── Makefile                   # Development commands
└── README.md                  # This file
```

## Getting Started

### Prerequisites

#### Required CLIs

Before getting started, ensure you have the following CLIs installed:

- **uv** - Python package manager and version manager
- **make** - For running development tasks and commands
- **Git** - For version control
- **Docker** - For containerization and running the dev container
- **Google Cloud CLI (`gcloud`)** - For interacting with Google Cloud Platform
- **Terraform** - For managing infrastructure

### Running with Dev Container

We provide a pre-configured development container to ensure a consistent development environment across all team members.

#### Using VS Code Dev Container

1. **Install Required Extensions:**
   - Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in VS Code

2. **Open the Project:**
   - Open the `/Research-Agent` folder in VS Code
   - You should see a notification suggesting to "Reopen in Container"
   - Click **"Reopen in Container"** or use the command palette:
     - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
     - Type **"Dev Containers: Reopen in Container"**
     - Press Enter

3. **Development Environment Ready:**
   - VS Code will build and start the dev container
   - All required dependencies will be pre-installed
   - You'll have access to all CLIs and tools mentioned above

#### Benefits of Using Dev Container

- **Consistency** - Same environment for all developers, eliminating "works on my machine" issues
- **Isolation** - Dependencies don't conflict with your host machine
- **Pre-configured** - All CLIs, Python packages, and tools are already installed
- **Easy Cleanup** - Remove the container without affecting your host system
- **Team Alignment** - Everyone uses the same development setup

#### Running Commands in Dev Container

Once inside the container, you can use the Makefile for common tasks:

```bash
# Install dependencies
uv sync --all-groups

# Run agent tests
make test-agent

# Run MCP tests
make run-bq-tests
make run-gcs-tests
```

## How to Contribute

We follow a standard Git workflow for contributions:

### 1. Create a Feature Branch

```bash
# Update main branch first
git checkout main
git pull origin main

# Create a new branch for your feature
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - For new features
- `bugfix/` - For bug fixes
- `docs/` - For documentation updates
- `refactor/` - For code refactoring

### 2. Make Your Changes

- Write clean, well-documented code
- Follow the existing code style and patterns
- Add or update tests as needed
- Update relevant documentation

### 3. Commit Your Changes

```bash
git add .
git commit -m "Clear, descriptive commit message"
```

### 4. Push to Remote

```bash
git push origin feature/your-feature-name
```

### 5. Submit a Pull Request

- Go to the GitHub repository
- You should see a prompt to create a Pull Request for your branch
- Click **"Compare & pull request"**
- Provide a clear title and description of your changes
- Reference any related issues using `#issue-number`
- Request review from team members
- Address any comments or requested changes

### 6. Merge

Once approved by at least one reviewer:
- Squash and merge commits (preferred for clean history)
- Delete the branch after merging

## Development Workflow

### Infrastructure Validation

Useful local verification targets:

```bash
make verify-agent-ci
make verify-bq-ci
make verify-gcs-ci
make verify-all-ci
```

For the GCS Terraform module specifically:
### Infrastructure Tests

Use this command to validate the GCS MCP Terraform module:

```bash
make test-gcs-terraform
```

This runs `terraform fmt -check -recursive`, `terraform init -backend=false`, and `terraform test` inside `terraform/gcs_mcp_server_resources`.

### Trigger Commands

Use these commands from repository root to create or refresh Cloud Build triggers for MCP Terraform stacks:

```bash
make run-once-terraform-triggers
```

Backward-compatible aliases:

```bash
make run-once-mcp-triggers
```

### One-Time Shared Resources Apply

Apply `shared_resources` once for the shared Artifact Registry state:

```bash
cd terraform/shared_resources
terraform init -reconfigure \
   -backend-config="bucket=<PROJECT_ID>-terraform-state" \
   -backend-config="prefix=terraform/state/shared-resources"
terraform plan
terraform apply
```

`bootstrap.sh` now runs this sequence by default. To skip it:

```bash
APPLY_SHARED_RESOURCES=false ./terraform/scripts/bootstrap.sh
```

Convenience Make targets:

```bash
make bootstrap
make bootstrap-no-shared
```
This target runs:
- `terraform fmt -check -recursive`
- `terraform init -backend=false`
- `terraform test`

It executes inside `terraform/gcs_mcp_server_resources`.

### Setting Up for Development

```bash
# Install dependencies using uv
uv sync --all-groups
```

### Running the Agent

```bash
# Example command (adjust based on actual implementation)
make run-ui-agent
```

### Running MCP Servers Locally

```bash
make run-bq-mcp-locally
make run-gcs-mcp-locally
```

For the GCS MCP smoke test:

```bash
make run-gcs-mcp-smoke BUCKET=my-bucket PREFIX=docs/
```

## Documentation

For detailed information about specific topics:

- **ADK Introduction** - See [docs/ADK-Intro.md](docs/ADK-Intro.md) for detailed information about the Agent Development Kit
- **Core Agent** - See [agent/core_agent/README.md](agent/core_agent/README.md)
- **BigQuery MCP Server** - See [mcp_servers/big_query/README.md](mcp_servers/big_query/README.md)
- **GCS MCP Server** - See [mcp_servers/gcs/README.md](mcp_servers/gcs/README.md)
- **Terraform Infrastructure** - See [terraform/README.md](terraform/README.md)
- **Model Armor** - See [notebooks/model_armor.ipynb](notebooks/model_armor.ipynb) for model safeguards exploration
