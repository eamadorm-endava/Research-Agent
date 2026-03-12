# Research-Agent

An AI-powered research agent platform combining the Agent Development Kit (ADK) with advanced Google Cloud Platform integrations through a Model Context Protocol (MCP) server.

## Overview

This repository contains two main features/projects:

### 1. Agent Development using the ADK
Build and customize intelligent agents using the Agent Development Kit. This framework provides all the necessary tools and utilities to develop, test, and deploy AI agents that can interact with various data sources and services.

### 2. MCP Server for GCP Services
A comprehensive Model Context Protocol (MCP) server that connects with different Google Cloud Platform (GCP) services, including:
- **BigQuery** - Query and analyze large datasets
- **Cloud Storage (GCS)** - Manage cloud storage buckets and objects
- **Google Drive** - Access and manage documents

**Key Differentiator:** Unlike current Google MCP servers, our implementation supports **write operations** in addition to read operations, enabling agents to create, update, and modify data in these services.

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
├── connectors/                 # Individual service connectors
│   │                           # Serves as tools for the agent
│   │                           # Will be wrapped in mcp_server in future
│   └── ...
│
├── mcp_server/                 # MCP Server implementation
│   │                           # Integrates connectors for protocol compliance
│   └── ...
│
├── terraform/                  # Infrastructure as Code
│   │                           # Service Accounts (SAs), IAM Permissions
│   │                           # and other required infrastructure
│   └── ...
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
- **Terraform** - For managing infrastructure (if deploying infrastructure)

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
make install

# Run tests (if configured)
make test

# Build/compile (if needed)
make build

# View all available commands
make help
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

## Documentation

For detailed information about specific topics:

- **ADK Introduction** - See [docs/ADK-Intro.md](docs/ADK-Intro.md) for detailed information about the Agent Development Kit
- **Model Armor** - See [notebooks/model_armor.ipynb](notebooks/model_armor.ipynb) for model safeguards exploration
