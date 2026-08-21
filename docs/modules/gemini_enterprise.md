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
│   ├── ge_manager.sh         # Core management CLI (create/delete app, auths, register/unregister agent)
│   ├── create_resources.sh   # Stage 1 creation script (enables APIs and provisions GE App)
│   └── delete_resources.sh   # Stage 1 deletion script (tears down GE App)
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

## 4. Lifecycle Management

### 4.1 Provisioning
- **Stage 1 (Prototyping)**: Execute `gemini_enterprise/scripts/create_resources.sh` (or `make create-ge-app`) to enable APIs and provision the App Engine.
- **Stage 2 (IaC & Production)**: Apply `terraform/gemini_enterprise_resources` for Terraform-managed APIs and IAM roles.

### 4.2 Teardown
- **Agent & Auth Cleanup**: Execute `gemini_enterprise/scripts/ge_manager.sh unregister-agent` and `delete-auth-ids`.
- **App & Terraform Teardown**: Execute `gemini_enterprise/scripts/delete_resources.sh` (or `make delete-ge-app`) and destroy `terraform/gemini_enterprise_resources`.

---

## 5. Security & IAM

The Gemini Enterprise Terraform stack provisions the following IAM roles for the automation service account (`terraform-sa-gemini-project`):
- `roles/discoveryengine.admin`
- `roles/secretmanager.secretAccessor`
