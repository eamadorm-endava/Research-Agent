# AI Agents in Gemini Enterprise

This repository is planned to be an accelerator for implementing Gemini Enterprise in any company; allowing to integrate AI Agents capable of reading/writing data from multiple sources, such as:

- Google Drive
- Google Cloud Storage
- BigQuery
- Google Calendar

using the user's permissions to access it, leveraging full AI Agent's capabilities to solve different use cases within a company.

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
        User(["<b>User Query</b><br/>Gemini Enterprise"])
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
        BQ_Pipe["<b>BQ Pipeline</b>"]
        GCS_Pipe["<b>GCS Pipeline</b>"]
        Drive_Pipe["<b>Drive Pipeline</b>"]
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