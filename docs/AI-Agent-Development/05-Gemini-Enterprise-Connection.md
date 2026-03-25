# Connecting the Agent to Gemini Enterprise

Once the agent is live in the Agent Engine runtime, it can be seamlessly integrated into **[Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/overview)** as a native corporate tool.

## Setup Steps

1. **Create App**: Ensure you have an active Gemini Enterprise environment.
2. **Configure Authorizations (If applicable)**: If your MCP Servers require OAuth, register an Authorization Resource in Gemini Enterprise first. **Follow the [OAuth for Gemini Enterprise Guide](./06-OAuth-Inside-Gemini-Enterprise.md)**.
3. **Register the Agent**: Connect your Agent Engine `RESOURCE_ID` (from step 04) to the GCP Console to register it within Gemini Enterprise. [See Register an ADK Agent](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent?hl=en#register-an-adk-agent).
4. **Assign Permissions**: Grant access to specific users or groups to interact with the agent natively from the Gemini chat interface. [See Set Permissions](https://docs.cloud.google.com/gemini/enterprise/docs/data-agent?hl=en#set-permissions).

---

## Troubleshooting

### `PERMISSION_DENIED: reasoning engine resource is not active`

If you receive a `500 INTERNAL` API error in Gemini Enterprise stating that the Reasoning Engine failed with `PERMISSION_DENIED`:

```json
{
  "error": {
    "code": 500,
    "message": "Reasoning Engine Execution Service stream failed with status code PERMISSION_DENIED..."
  }
}
```

**Resolution**: The background Service Agent account used by Gemini Enterprise (e.g., `service-[project-number]@gcp-sa-discoveryengine.iam.gserviceaccount.com`) lacks permission to trigger Vertex AI or call the MCP Server.

Grant the following IAM roles to the Discovery Engine Service Agent in your GCP project:
- **Vertex AI User** (`roles/aiplatform.user`)
- **Discovery Engine User** (`roles/discoveryengine.user`)
- **Cloud Run Invoker** (`roles/run.invoker`)
