# Connect an AI-Agent deployed in Agent Engine to Gemini Enterprise

Once the agent is deployed in the Agent Engine runtime, the main objective is to use this agent directly within [Gemini Enterprise](https://docs.cloud.google.com/gemini/enterprise/docs/overview). 

To connect the agent, follow these main steps:

1. **Create a Gemini Enterprise App**: Ensure you have a Gemini Enterprise environment set up.
2. **Create OAuth Credentials (Optional)**: If your agent requires accessing resources (e.g., Google Drive, BigQuery) on the user's behalf, create an OAuth 2.0 Web Client for each tool. [See documentation](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent?hl=en#authorize-your-adk-agent).

   *If the agent does not need to access GCP resources on the user's behalf, this step can be skipped.
3. **Register the Agent**: Connect the Agent Engine resource to the GCP Console to register it within Gemini Enterprise. [See documentation](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent?hl=en#register-an-adk-agent).
4. **Add Permissioned Users**: Grant access to the specific users who should be able to interact with the agent. [See documentation](https://docs.cloud.google.com/gemini/enterprise/docs/data-agent?hl=en#set-permissions).

---

## Troubleshooting

### `PERMISSION_DENIED` Error

If, when interacting with the agent in Gemini Enterprise, you receive an error similar to this:

```json
{
 "error": {
  "code": 500,
  "message": "Agent failed with error: Reasoning Engine Execution Service stream failed with status code PERMISSION_DENIED: The reasoning engine resource [projects/project-id/locations/location/reasoningEngines/resource-id] is not active.",
  "status": "INTERNAL",
  "details": [
   {
    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
    "reason": "REMOTE_AGENT_FAILURE",
    "domain": "discoveryengine.googleapis.com"
   },
   {
    "@type": "type.googleapis.com/google.rpc.RequestInfo",
    "requestId": "assist_token:assist-token-value"
   }
  ]
 }
}
```

Please make sure that the background service agent account used by Gemini Enterprise (which typically looks like `service-[project-number]@gcp-sa-discoveryengine.iam.gserviceaccount.com`) has the following IAM permissions assigned in your GCP project:

- **Discovery Engine Admin** (`roles/discoveryengine.admin`)
- **Vertex AI User** (`roles/aiplatform.user`)
