# Gemini Enterprise Module

Independent module to manage Gemini Enterprise (Vertex AI Search / Discovery Engine) applications, OAuth Authorizations, and ADK Agent registrations.

## Overview

Gemini Enterprise allows organizations to unify search across enterprise data stores and orchestrate conversational AI agents. This module provides:
1. **Lifecycle Scripts**: Idempotent provisioning and teardown of the Gemini Enterprise App (`APP_TYPE_INTRANET`).
2. **Unified CLI (`ge_manager.sh`)**:
   - `create-ge-app`: Provision a search engine.
   - `delete-ge-app`: Delete a search engine.
   - `create-auth-ids`: Create OAuth authorizations for Google Workspace, Microsoft Entra, and Atlassian.
   - `delete-auth-ids`: Delete OAuth authorizations.
   - `register-agent`: Register a Vertex AI Reasoning Engine with automated fallback resolution of the Agent Runtime ID.
   - `unregister-agent`: Unregister an agent by display name.

## Directory Structure

```text
gemini_enterprise/
├── scripts/
│   ├── create_resources.sh   # Provisions APIs and the GE App
│   ├── delete_resources.sh   # Tears down the GE App
│   └── ge_manager.sh         # Core management CLI
└── README.md
```

## Usage Examples

### 1. Provisioning
```bash
./gemini_enterprise/scripts/create_resources.sh \
  --project "<PROJECT_ID>" \
  --ge-location "global" \
  --ge-app-name-suffix "osiris-app"
```

### 2. Registering an Agent
```bash
./gemini_enterprise/scripts/ge_manager.sh register-agent \
  --project "<PROJECT_ID>" \
  --ge-location "global" \
  --app-id "<PROJECT_ID>-global-osiris-app" \
  --agent-display-name "OSIRIS" \
  --agent-engine-location "us-central1"
```

### 3. Teardown
```bash
./gemini_enterprise/scripts/delete_resources.sh \
  --project "<PROJECT_ID>" \
  --ge-location "global" \
  --ge-app-name-suffix "osiris-app"
```
