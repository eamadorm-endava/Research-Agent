# Infrastructure

This repository contains all the terraform modules to deploy the resources required by the AI Agent and the MCP Server.

## Folder Structure

```
. 
├── ai_agent_resources/ # Full infrastructure required by the AI Agent 
├── mcp_server_resources/ # Full infrastructure required by the MCP Server 
├── base_modules/ # Root modules used to build the ai_agent and mcp_server resources 
└── README.md
```

This allows to fully deploy the AI Agent and MCP Server independently.

## How to Deploy the Resources

### AI Agent


Open the terminal in the `ai_agent_resources/` directory and run the following commands:

```bash
terraform init
terraform apply
```

## MCP Server


Open the terminal in the `mcp_server_resources/` directory and run the following commands:

```bash
terraform init
terraform apply
```
