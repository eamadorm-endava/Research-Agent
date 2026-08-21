# Module Documentation - Gemini Enterprise

This module manages the lifecycle, APIs, OAuth 2.0 authorizations, and ADK Agent registrations for **Gemini Enterprise** (Vertex AI Search / Discovery Engine).

---

## 1. Architecture & Design Principles

Gemini Enterprise is fully decoupled from the AI Agent codebase:
1. **Independent Lifecycle**: Gemini Enterprise apps and configurations can be deployed, reconfigured, or deleted without modifying or redeploying the core AI Agent.
2. **Dynamic Reasoning Engine Resolution**: The registration CLI (`ge_manager.sh register-agent`) dynamically resolves the reasoning engine resource ID from Vertex AI if not explicitly provided.
3. **Conditional Registration**: The AI Agent CI/CD pipeline deploys the Vertex AI Agent Engine and conditionally handles OAuth authorizations and GE registration only when `_REGISTER_AGENT_IN_GE="true"`.

---

## 2. Directory Structure

```text
gemini_enterprise/
├── scripts/
│   └── ge_manager.sh         # Core management CLI (create/delete app, auths, register/unregister agent)
└── README.md                 # Module usage and command references

terraform/gemini_enterprise_resources/
├── main.tf                   # Enables discoveryengine & dialogflow APIs and IAM roles
├── variables.tf              # Input variables
├── terraform.tfvars          # Default variables
├── versions.tf               # Terraform and provider constraints
└── backend.tf                # Remote GCS backend configuration
```

---

## 3. CLI Subcommands (`ge_manager.sh`)

| Command | Description | Required Parameters |
|---|---|---|
| `create-ge-app` | Creates a Gemini Enterprise intranet app engine | `--project`, `--app-id` (or `--ge-app-id`), `[--ge-location]` |
| `delete-ge-app` | Deletes a Gemini Enterprise intranet app engine | `--project`, `--app-id` (or `--ge-app-id`), `[--ge-location]` |
| `create-auth-ids` | Creates OAuth 2.0 authorization configurations | `--project`, `--auth-ids`, `--client-id`, `--client-secret`, `--scopes`, `--auth-uri-base`, `--token-uri`, `[--ge-location]` |
| `delete-auth-ids` | Deletes OAuth 2.0 authorization configurations | `--project`, `--auth-ids`, `[--ge-location]` |
| `register-agent` | Registers an ADK reasoning engine into the GE App | `--project`, `--app-id`, `--agent-display-name`, `--agent-engine-location`, `[--agent-engine-agent-id]`, `[--auth-ids]`, `[--ge-location]` |
| `unregister-agent` | Unregisters an agent by its display name | `--project`, `--app-id`, `--agent-display-name`, `[--ge-location]` |

---

## 4. Orchestration Integration

### 4.1 Master Creation (`creation_manager.sh`)
- **Step 6**: Deploys Gemini Enterprise Terraform resources and executes `ge_manager.sh create-ge-app`.
- **Step 7**: Deploys the AI Agent and injects `_REGISTER_AGENT_IN_GE` into the Cloud Build trigger substitution parameters.

### 4.2 Master Deletion (`deletion_manager.sh`)
- **Step 1**: Unregisters the agent and deletes OAuth authorization IDs via `ge_manager.sh`.
- **Step 3**: Deletes the GE App via `ge_manager.sh delete-ge-app` and destroys `terraform/gemini_enterprise_resources`.

---

## 5. Security & IAM

The Gemini Enterprise Terraform stack provisions the following IAM roles for the automation service account (`terraform-sa-gemini-project`):
- `roles/discoveryengine.admin`
- `roles/secretmanager.secretAccessor`
