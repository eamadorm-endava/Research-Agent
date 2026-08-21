# Agent Gateway Module (Internal Load Balancer & Private DNS)

This module provisions an enterprise-grade, 100% private networking layer connecting **Vertex AI Agent Engine** to **Cloud Run MCP Microservices** via a Regional Internal Application Load Balancer and Private Cloud DNS.

---

## Architectural Overview

```text
[ Vertex AI Agent Engine ]
          │
          │ (VPC Peering / Direct VPC Egress)
          ▼
   [ Cloud DNS Private Zone: gateway.mcp.internal ]
          │
          ▼
   [ Regional Internal Application Load Balancer (Envoy L7) ]
          │
          ├── /bq/*         ──> [ Serverless NEG: bigquery-mcp-server ]
          ├── /drive/*      ──> [ Serverless NEG: drive-mcp-server ]
          ├── /gcs/*        ──> [ Serverless NEG: gcs-mcp-server ]
          ├── /calendar/*   ──> [ Serverless NEG: calendar-mcp-server ]
          ├── /onedrive/*   ──> [ Serverless NEG: onedrive-mcp-server ]
          ├── /outlook/*    ──> [ Serverless NEG: outlook-mcp-server ]
          ├── /sharepoint/* ──> [ Serverless NEG: sharepoint-mcp-server ]
          ├── /atlassian/*  ──> [ Serverless NEG: atlassian-mcp-server ]
          └── /ekb/*        ──> [ Serverless NEG: ekb-pipeline ]
```

---

## Key Features

1. **Strict Ingress Enforcement**:
   - All Cloud Run microservices enforce `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`.
   - External requests to `*.run.app` are rejected at the edge.

2. **Regional Envoy Proxy & Serverless NEGs**:
   - Uses a dedicated proxy-only subnet (`purpose = "REGIONAL_MANAGED_PROXY"`).
   - Routes traffic to Cloud Run serverless network endpoint groups.
   - Automatically rewrites path prefixes (e.g. `/outlook/mcp` $\rightarrow$ `/mcp`).

3. **Private Cloud DNS (`mcp.internal`)**:
   - Managed private DNS zone linked to the customer VPC.
   - Maps `gateway.mcp.internal` to the Internal IP of the Forwarding Rule.

---

## Configuration & Usage

### Provisioning via Terraform
```bash
cd terraform/agent_gateway_resources
terraform init -backend-config="bucket=<PROJECT_ID>-terraform-state" -backend-config="prefix=terraform/state/agent-gateway-resources"
terraform plan -var="project_id=<PROJECT_ID>" -var="main_region=us-central1"
terraform apply -auto-approve -var="project_id=<PROJECT_ID>" -var="main_region=us-central1"
```

### Endpoints Injected into AI Agent
- `BIGQUERY_URL=http://gateway.mcp.internal/bq`
- `DRIVE_URL=http://gateway.mcp.internal/drive`
- `GCS_URL=http://gateway.mcp.internal/gcs`
- `CALENDAR_URL=http://gateway.mcp.internal/calendar`
- `ONEDRIVE_URL=http://gateway.mcp.internal/onedrive`
- `OUTLOOK_URL=http://gateway.mcp.internal/outlook`
- `SHAREPOINT_URL=http://gateway.mcp.internal/sharepoint`
- `ATLASSIAN_URL=http://gateway.mcp.internal/atlassian`
- `EKB_PIPELINE_URL=http://gateway.mcp.internal/ekb`
