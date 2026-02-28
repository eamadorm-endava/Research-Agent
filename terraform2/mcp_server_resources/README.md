# MCP Server Resources

This directory contains the Terraform configuration for the MCP Server.

## APIs

The following APIs are managed (enabled) by this module.
This APIs must be enabled before deploying the MCP Server in any GCP project.

- storage.googleapis.com
- drive.googleapis.com
- docs.googleapis.com
- bigquery.googleapis.com

## Service Accounts & Permissions

Permissions are managed (assigned) by this module. It creates the service account and assigns the required permissions to it.

| Service Account Name | Created/Edited | Description | Permissions |
|---|---|---|---|
| mcp-server | Created | This SA is used by the MCP server. | <ul><li>Storage Object User</li><li>BigQuery Data Viewer</li><li>BigQuery Job User</li></ul> |
