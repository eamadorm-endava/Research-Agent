# ADR-003: Network Strategy for MCP Servers and Agent Runtime

**Status**: Accepted  
**Date**: August 21, 2026  
**Owner**: Cloud Architecture & DevOps / Platform Engineering  
**Related Systems**: Vertex AI Reasoning Engine (Agent Engine), Cloud Run MCP Servers, EKB Pipeline, Regional Internal Application Load Balancer (ILB), Serverless NEGs, Cloud DNS, VPC Networking  

---

## 1. Context

The Research-Agent architecture integrates an AI Agent running inside the **Vertex AI Agent Engine (ADK Runtime)** with a suite of microservices deployed as **Google Cloud Run** containers:
- Model Context Protocol (MCP) Servers (BigQuery, Google Drive, GCS, Google Calendar, Microsoft OneDrive, Microsoft Outlook, Microsoft SharePoint, Atlassian Jira/Confluence).
- Enterprise Knowledge Base (EKB) ingestion pipeline.

### The Security & Networking Challenge
Enterprise security baselines and Organization Policies require that all Cloud Run backend microservices enforce **internal ingress only** (`INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` or `INGRESS_TRAFFIC_INTERNAL_ONLY`), strictly prohibiting direct public internet access.

When Cloud Run services enforce internal ingress:
1. Google Front End (GFE) disables public DNS resolution and edge routing for the default `https://<service-name>-<hash>.a.run.app` URLs.
2. The managed Vertex AI Agent Engine runtime, when attempting direct HTTPS calls to those default Cloud Run URLs, fails with `HTTP 404 Not Found` or `HTTP 403 Forbidden: Access blocked by ingress settings`.

Therefore, a robust, private networking layer was required to bridge the managed Vertex AI Agent Engine with internal-only Cloud Run microservices.

---

## 2. Decision

A **Regional Internal Application Load Balancer (L7 Envoy-based ILB)** will be implemented, paired with **Serverless Network Endpoint Groups (NEGs)** and a **Private Cloud DNS Zone (`mcp.internal`)** within the Customer VPC.

All Cloud Run services standardize on:
```hcl
service_config = {
  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}
```

The AI Agent routes all MCP tool invocations to the centralized internal gateway domain `http://gateway.mcp.internal/<service_path>`, which rewrites the path prefix and routes internally across private Google infrastructure.

---

## 3. Architectural Topology & Two-Tier Communication Model

The architecture establishes a strict **Two-Tier Communication Model**:
1. **Tier 1 (Control Plane - Gemini Enterprise to Agent Engine)**: Operates over Google's managed API control plane (`aiplatform.googleapis.com`). Gemini Enterprise invokes the Agent Engine using IAM authorization (`roles/aiplatform.user`). This layer is completely decoupled from VPC ingress restrictions, allowing Gemini Enterprise to seamlessly dispatch user queries and receive streamed responses.
2. **Tier 2 (Data Plane - Agent Engine to Cloud Run MCP Microservices)**: Operates 100% within the Customer VPC. When the agent decides to invoke an MCP tool, traffic is routed through the Regional Internal Application Load Balancer and Private Cloud DNS directly to the private Cloud Run containers.

```mermaid
flowchart TD
    subgraph ClientLayer["User Interface & Enterprise Search Layer"]
        User["Enterprise User"]
        GE["Gemini Enterprise (Discovery Engine / App Engine)"]
    end

    subgraph VertexTenant["Vertex AI Managed Control Plane"]
        AE["Vertex AI Agent Engine (ADK Runtime)"]
    end

    subgraph CustomerVPC["Customer VPC Network (e.g., default / custom-vpc)"]
        subgraph Subnets["VPC Subnets (us-central1)"]
        subgraph ClientTier["Client Subnet (Application Subnet)"]
            NetAttach["Compute Engine Network Attachment (PSC-I)"]
            PrivateDNS["Private Cloud DNS (mcp.internal)"]
            FwdRule["Internal Forwarding Rule (10.10.0.2:80)"]
        end

        subgraph ProxySubnet["Proxy-Only Subnet (10.129.0.0/23)"]
            TargetProxy["Target HTTP Proxy"]
            URLMap["Regional URL Map & URL Rewrites"]
        end

        subgraph Backends["Backend Services (load_balancing_scheme = INTERNAL_MANAGED)"]
            BS_BQ["Backend Service: BigQuery"]
            BS_DRV["Backend Service: Drive"]
            BS_GCS["Backend Service: GCS"]
            BS_CAL["Backend Service: Calendar"]
            BS_ONE["Backend Service: OneDrive"]
            BS_OUT["Backend Service: Outlook"]
            BS_SP["Backend Service: SharePoint"]
            BS_EKB["Backend Service: EKB Pipeline"]
        end

        subgraph NEGs["Serverless Network Endpoint Groups"]
            NEG_BQ["Serverless NEG: bigquery-mcp-server"]
            NEG_DRV["Serverless NEG: drive-mcp-server"]
            NEG_GCS["Serverless NEG: gcs-mcp-server"]
            NEG_CAL["Serverless NEG: calendar-mcp-server"]
            NEG_ONE["Serverless NEG: onedrive-mcp-server"]
            NEG_OUT["Serverless NEG: outlook-mcp-server"]
            NEG_SP["Serverless NEG: sharepoint-mcp-server"]
            NEG_EKB["Serverless NEG: ekb-pipeline"]
        end

        subgraph CloudRun["Cloud Run Microservices (INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER)"]
            CR_BQ["bigquery-mcp-server"]
            CR_DRV["drive-mcp-server"]
            CR_GCS["gcs-mcp-server"]
            CR_CAL["calendar-mcp-server"]
            CR_ONE["onedrive-mcp-server"]
            CR_OUT["outlook-mcp-server"]
            CR_SP["sharepoint-mcp-server"]
            CR_EKB["ekb-pipeline"]
        end
    end

    User -->|"Web Query"| GE
    GE ==>|"Tier 1: Vertex AI API Call - IAM Auth"| AE
    AE ==>|"Tier 2: PSC-I Network Attachment & DNS Peering"| NetAttach
    NetAttach --> PrivateDNS
    NetAttach ==>|"HTTP POST to http://gateway.mcp.internal/bq/mcp"| FwdRule
    FwdRule --> TargetProxy --> URLMap
    
    URLMap -->|"/bq/* -> rewrite /"| BS_BQ --> NEG_BQ --> CR_BQ
    URLMap -->|"/drive/* -> rewrite /"| BS_DRV --> NEG_DRV --> CR_DRV
    URLMap -->|"/gcs/* -> rewrite /"| BS_GCS --> NEG_GCS --> CR_GCS
    URLMap -->|"/calendar/* -> rewrite /"| BS_CAL --> NEG_CAL --> CR_CAL
    URLMap -->|"/onedrive/* -> rewrite /"| BS_ONE --> NEG_ONE --> CR_ONE
    URLMap -->|"/outlook/* -> rewrite /"| BS_OUT --> NEG_OUT --> CR_OUT
    URLMap -->|"/sharepoint/* -> rewrite /"| BS_SP --> NEG_SP --> CR_SP
    URLMap -->|"/ekb/* -> rewrite /"| BS_EKB --> NEG_EKB --> CR_EKB
```

---

## 4. Communication Flows: Gemini Enterprise vs. Cloud Run MCPs

### 4.1. Tier 1: Gemini Enterprise to Vertex AI Agent Engine
* **Protocol & Endpoint**: HTTPS requests directed to Google Cloud's managed Vertex AI APIs (`https://<region>-aiplatform.googleapis.com/v1/projects/<project>/locations/<region>/reasoningEngines/<id>:query` and `:streamQuery`).
* **Authentication**: Google Cloud IAM service-to-service authorization using the Gemini Enterprise service identity granted `roles/aiplatform.user`.
* **Network Boundary**: Public Google API Control Plane. Because this is a native Google Cloud service-to-service interaction, it is **completely unaffected** by VPC subnets or Cloud Run internal ingress restrictions. Gemini Enterprise can always discover, invoke, and stream responses from the Agent Engine.

### 4.2. Tier 2: Vertex AI Agent Engine to Cloud Run MCP Microservices
* **Protocol & Endpoint**: HTTP requests to `http://gateway.mcp.internal/<service-path>/mcp`.
* **Authentication**: Layer 7 application token verification (Google OAuth 2.0 PKCE user-delegated access tokens passed in `Authorization: Bearer <token>` and Service Account ID tokens in `X-Serverless-Authorization`).
* **Network Boundary & PSC-I Egress**: 100% Private VPC Data Plane. Vertex AI Agent Engine connects to the customer VPC via a dedicated **Compute Engine Network Attachment (`google_compute_network_attachment`)** and **Cloud DNS Peering** (`roles/dns.peer`). When the Agent Engine initiates an MCP tool call, the request exits into `mcp-agent-vpc`, resolves `gateway.mcp.internal` through Private Cloud DNS, hits the Regional Internal Load Balancer on port 80, and is routed via Serverless NEGs directly to the Cloud Run microservices enforcing `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`.

---

## 5. Component Definitions

### 5.1. Compute Engine Network Attachment (`PSC-I`)
* Dedicated network attachment created in the application subnetwork (`google_compute_subnetwork.app_subnet`). It provides the Private Service Connect interface (PSC-I) that allows Vertex AI Agent Engine instances running in the Google tenant project to send egress traffic directly into the customer VPC network.

### 5.2. Cloud DNS Peering (`roles/dns.peer`)
* Grants the Vertex AI Service Agent identity (`service-<project-number>@gcp-sa-aiplatform.iam.gserviceaccount.com`) permission to peer with the customer VPC's Cloud DNS private zone `mcp.internal`, ensuring domain queries from the agent container resolve to the internal forwarding rule IP.

### 5.3. Proxy-Only Subnetwork (`REGIONAL_MANAGED_PROXY`)
* **Purpose**: Google Cloud's Regional Internal Application Load Balancer relies on Envoy proxies running within a dedicated subnet reserved exclusively for load balancer proxies (`purpose = "REGIONAL_MANAGED_PROXY"`, `role = "ACTIVE"`).
* **CIDR Range**: `10.129.0.0/23` allocated within the region (`us-central1`).

### 5.4. Serverless Network Endpoint Groups (Serverless NEGs)
* **Purpose**: Serverless NEGs (`google_compute_region_network_endpoint_group` of type `SERVERLESS`) act as the native GCP bridge connecting the Load Balancer's backend services to Cloud Run without requiring Compute Engine VMs or manual NAT configurations.
* **Granularity**: One Serverless NEG is created per Cloud Run service.

### 5.3. URL Map & Path Prefix Rewriting
* **Purpose**: Provides a unified entry point (`gateway.mcp.internal`) with path-based routing:
  * `http://gateway.mcp.internal/bq/mcp` $\rightarrow$ routes to `bigquery-mcp-server` at `/mcp`
  * `http://gateway.mcp.internal/outlook/mcp` $\rightarrow$ routes to `outlook-mcp-server` at `/mcp`
  * `http://gateway.mcp.internal/drive/mcp` $\rightarrow$ routes to `drive-mcp-server` at `/mcp`
* **Route Action**: Uses `path_prefix_rewrite = "/"` to strip the path prefix so that the underlying FastMCP server receives its expected `/mcp` root endpoint without modifying the Python application code.

### 5.4. Private Cloud DNS (`google_dns_managed_zone`)
* **Zone Name**: `mcp-internal-zone` (`mcp.internal.`)
* **Scope**: Visibility is set to `private`, linked directly to the VPC network.
* **Records**: An `A` record (`gateway.mcp.internal`) and wildcard (`*.mcp.internal`) resolving to the Internal IP of the Load Balancer Forwarding Rule.

---

## 6. Evaluated Options

### Option A. Public Ingress (`INGRESS_TRAFFIC_ALL`) + Application-Level Auth (Zero Trust)
* **Pros**: Zero additional infrastructure cost; instantaneous setup.
* **Cons**: Violates strict organizational policies requiring internal-only ingress for backend Cloud Run services; traffic traverses public Google Edge endpoints.
* **Verdict**: Rejected due to organizational compliance requirements.

### Option B. Regional Internal Application Load Balancer (ILB) + Serverless NEGs (Selected)
* **Pros**:
  * 100% private: Traffic stays completely inside Google's private network backbone.
  * Complies with `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` organization policies.
  * Highly scalable: Serverless NEGs scale up and down automatically with Cloud Run instances.
  * Clean DNS and routing: Single entry point `gateway.mcp.internal` for all MCP servers.
* **Cons**: Requires allocating a proxy-only subnet and maintaining the Load Balancer Terraform stack.
* **Verdict**: **Accepted** as the official network architecture.

### Option C. Private Service Connect (PSC) Endpoints per Service
* **Pros**: Direct point-to-point private connectivity.
* **Cons**: High operational overhead: requires managing individual PSC endpoints, IP allocations, and service attachments for every single MCP service independently.
* **Verdict**: Rejected in favor of the unified URL Map design of Option B.

---

## 7. Consequences

### 7.1. Positive
* **Full Network Isolation**: MCP servers and EKB pipelines cannot be reached or probed from the public internet.
* **Simplified Configuration**: Developers and agents target a single, consistent internal domain (`http://gateway.mcp.internal/<service_prefix>`) instead of managing dynamic, random Cloud Run hash URLs.
* **Defense-in-Depth**: In addition to private network isolation, all MCP servers still enforce **Layer 7 Application Security** via OAuth 2.0 PKCE user-delegated tokens and `roles/run.invoker` IAM checks.

### 7.2. Negative / Operational Notes
* **Terraform Stack Dependency**: The `agent_gateway_resources` Terraform stack must be deployed after MCP servers exist (so Cloud Run services are available for NEGs) and before the AI Agent is deployed (so the internal endpoints resolve).
* **Proxy-Only Subnet**: The VPC network must have IP address space available for the `10.129.0.0/23` proxy-only subnet in the deployment region.

---

## 8. Implementation Reference

* **Terraform Module**: [`terraform/agent_gateway_resources/`](../../terraform/agent_gateway_resources/)
* **Module Documentation**: [`docs/modules/agent_gateway.md`](../modules/agent_gateway.md)
* **Orchestrator Integration**: [`terraform/scripts/creation_manager.sh`](../../terraform/scripts/creation_manager.sh) (Step 5.5)
* **Cloud Run Base Module**: [`terraform/base_modules/cloud-run-v2/variables.tf`](../../terraform/base_modules/cloud-run-v2/variables.tf)
