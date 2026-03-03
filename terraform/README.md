## Infrastructure Management

This directory contains the Terraform configurations and bootstrap scripts required to manage the Research-Agent infrastructure on Google Cloud Platform.

## Prerequisites and Required Permissions

Before running any scripts, ensure your active account (the one you used to run gcloud auth login) has the following IAM roles at the Project Level:

- ```roles/resourcemanager.projectIamAdmin (To manage Service Account permissions)```

- ```roles/iam.serviceAccountAdmin (To create the Terraform SA)```

- ```roles/serviceusage.serviceUsageAdmin (To enable APIs)```

- ```roles/storage.admin (To create the State Bucket)```


## Infrastructure deployment workflow

The environment uses a dedicated Service Account and a GCS Backend to manage state securely via Cloud Build 2nd Gen.

1. Open your terminal (Cloud Shell or local).

2. Navigate to the scripts folder:

```
cd terraform/scripts/
```

3. Execute the Bootstrap script:

    - Check README.md inside script folder and follow the instructions

This script creates the Service Account, grants required IAM roles and permissions, creates the GCS state bucket, and sets up the Cloud Build Triggers.

#### Folder Structure and Resources

Once the bootstrap is complete, you can manage specific resources.

## Terraform Project Structure

| Folder                | Description                                              |
|-----------------------|----------------------------------------------------------|
| `base_modules/`       | Reusable modules (IAM, APIs, Networking).               |
| `ai_agent_resources/` | Service Accounts and APIs for the AI Agent.             |
| `mcp_server_resources/` | Cloud Run and Vertex AI setup for MCP.               |

For deployment details check:

- AI Agent Services: View README.md inside ai_agent_resources folder
- MCP Server Resources: View README.md inside mcp_server_resources folder

## CI/CD Workflow

The infrastructure is deployed automatically via Cloud Build:

1. CI (Terraform Plan): Triggered automatically when a Pull Request is opened against main. 
2. CD (Terraform Apply): Triggered automatically when code is Merged/Pushed to main.