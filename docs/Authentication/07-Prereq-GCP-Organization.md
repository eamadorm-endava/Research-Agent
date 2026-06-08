# Prerequisite 1: Google Cloud Organization ID

When configuring Workforce Identity Federation, the **Workforce Identity Pool** must be created at the Organization level in Google Cloud, rather than within a specific project. Because of this, having a Google Cloud Organization is a strict prerequisite.

## Why is an Organization Required?

In Google Cloud, an **Organization** is the root node of the Google Cloud resource hierarchy. 
- Workforce Identity Pools are intended to govern identities across your entire company, giving them the ability to access resources across many different projects. 
- Creating the pool at the Organization level ensures centralized security and administration.

## How to find your Organization ID

To run the CLI commands for creating a Workforce Identity Pool, you need your unique Organization ID. 

### Option 1: Using the Google Cloud CLI (gcloud)

You can list the organizations your user has access to by running the following command in your terminal:

```bash
gcloud organizations list
```

**Example Output:**
```text
DISPLAY_NAME            ID               DIRECTORY_CUSTOMER_ID
yourcompany.com         123456789012     A0b1c2d3e
```
In this example, the Organization ID you need for the CLI script is `123456789012`.

### Option 2: Using the Google Cloud Console

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. In the top navigation bar, click on the **Project drop-down** menu.
3. A modal window will appear. At the top of this modal, click the **Select from** dropdown and choose your organization.
4. Next to the organization name, you will see a numeric ID. This is your Organization ID.

## Required Permissions

To create a Workforce Identity Pool, the account running the `gcloud` commands must have the **Workforce Identity Pool Admin** (`roles/iam.workforcePoolAdmin`) role at the Organization level.
