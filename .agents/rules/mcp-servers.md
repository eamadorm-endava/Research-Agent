---
trigger: model_decision
description: This should only apply when the user ask to develop an MCP Server
---

# MCP Server Development Guidelines

This document outlines the standards and best practices for developing MCP servers in this repository.

## 1. Repository Folder Structure

Each MCP server directory (under `mcp_servers/`) must follow this standard structure:

- **`app/`**: Core source code for the MCP server and its clients.
- **`tests/`**: Unit and integration tests (using `pytest`).
- **`README.md`**: Comprehensive documentation of tools, installation, and usage.
- **`Dockerfile`**: Container definition for building the server image.
- **`scripts/`** (Optional): Utility scripts for local setup or smoke testing.
- **`__init__.py`**: Standard package identifier.

## 2. Architectural Patterns

### Client Management
- **Centralized Logic**: Every MCP server must have an internal client that manages all constraints, API connectors, and logic.
- **Single Responsibility**: Create one client per API or specific logic implementation.
- **Multi-Client Orchestration**: 
  - If a server requires multiple clients (e.g., Google Calendar and Google Meet), organize them into subfolders within `app/`.
  - Create a main connector/client in the `app/` folder that **must initialize all sub-clients in its `__init__` initializer**.
  - The main client should either delegate to sub-client public methods or combine them into higher-level logic.

### Client Structure
Each internal client should follow this module structure:
- `config.py`: Environment and constant configuration (using `pydantic-settings`).
- `schemas.py`: Pydantic models for data validation and API exchange.
- `main.py`: Entry point (renamed to something descriptive like `bigquery_client.py`).

### Shared Logic
- **`app/utils/`**: Shared logic, helper functions, or internal tools should be placed in a general `utils/` folder within the `app/` directory to be accessible by all clients and sub-clients.

### Method Visibility
- **Public Methods**: All public methods of the client must be designed to be wrapped as MCP Tools.
- **Private Methods**: Use `_method_name` for internal helpers that should only be called by other methods within the client.

## 2. Implementation Workflow

- **Client-First Development**: Fully develop and test the internal client and its API connectors before starting the MCP Server implementation.
- **MCP SDK**: Always use the Official MCP Python SDK for server implementation.
- **Authentication**: Always implement authentication through OAuth.
- **Statelessness**: The MCP Server must be stateless; it should only validate that a valid token is provided during tool execution, this includes validating required scopes based on the client requirements previously created.
- **Security Check**: Always investigate the official API documentation for the required scopes and ensure validation is performed directly by the MCP Server Middleware.

## 3. Patterns from Google Calendar & BigQuery

- **Modularization**: Follow the `google_calendar/app` pattern of separating APIs into sub-packages (`calendar/`, `meet/`).
- **Main Entry Point**: Use a `mcp_server.py` or `main.py` at the root of the app to define the FastMCP/MCP server and register tools from the client.
- **Testing**: Ensure consistent `Makefile` targets are added for both the internal client and the full MCP server.