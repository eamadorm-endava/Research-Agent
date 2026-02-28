# AI Agent Resources

This directory contains the Terraform configuration for the AI Agent.

## APIs

The following APIs are managed (enabled) under the `api_services/` directory.
This APIs must be enabled before deploying the AI Agent in any GCP project.

- aiplatform.googleapis.com
- modelarmor.googleapis.com

## Service Accounts & Permissions

Permissions are managed (assigned) under the `service_accounts/` directory. It creates/edits service accounts and assigns the required permissions to them.

| Service Account Name | Created/Edited | Description | Permissions |
|-|-|-|-|
| adk-agent | Created | This SA can be impersonated by a user/group that needs to develop or test the ADK Agent capabilities. | <ul><li>VertexAI User</li><li>ModelArmor User</li></ul> |
| Vertex AI Service Agent | Edited | This SA is created by Vertex AI and is used internally by Vertex AI to invoke, Gemini models, ModelArmor templates, and Agent engines | <ul><li>VertexAI User</li><li>ModelArmor User</li></ul> |


**Note*: The name of the service account can be easily changed by modifying the `service_account_name` variable in the `permissions/` directory.

