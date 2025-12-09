# Vertex AI Memory Bank MCP - Deployment Guide

This guide details the deployment of the Vertex AI Memory Bank MCP server to Google Cloud Run using a **Per-User (Single-Tenant)** architecture.

## Architecture Overview

-   **Isolation**: Each user gets a dedicated Cloud Run service (e.g., `memory-bank-user-123`).
-   **Execution**: The server runs **In-Process** using FastAPI + FastMCP to ensure performance and reliability.
-   **Provisioning**: Services are spawned dynamically via the `provisioning/provision_user.py` script (acting as the Control Plane).
-   **Security**: All endpoints require a `CONNECTOR_BEARER_TOKEN`. Backend access to Vertex AI is handled via the Service Account.

## Prerequisites

1.  **Google Cloud Project**: `directed-asset-479716-f6`
2.  **Service Account**: Must have `roles/aiplatform.user` and `roles/run.invoker`.
3.  **Local Tools**:
    -   Docker
    -   gcloud CLI
    -   Python 3.11+
    -   `pip install google-cloud-run`

## Deployment Workflow

### 1. Build the "Golden Image"

First, build and push the Docker image that serves as the template for all user services.

```bash
chmod +x build.sh
./build.sh
```

This pushes the image to: `gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest`

### 2. Provision a User Service

Use the provisioning script to spin up a dedicated service for a user.

```bash
# Example
python provisioning/provision_user.py \
  --project directed-asset-479716-f6 \
  --user-id "user_123" \
  --image "gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest" \
  --service-account "vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com" \
  --engine-name "projects/directed-asset-479716-f6/locations/us-central1/collections/default_collection/engines/agent-engine-user-123" \
  --token "secret-bearer-token-for-user-123"
```

**Output**:
```text
Service deployed successfully: https://memory-bank-user-123-xyz.a.run.app
```

### 3. Connect the MCP Client (Cursor)

Configure Cursor to connect to the new service URL via SSE.

**File**: `cursor/mcp.json` (or via Cursor Settings)

```json
{
  "mcpServers": {
    "memory-bank": {
      "command": "",
      "args": [],
      "env": {},
      "url": "https://memory-bank-user-123-xyz.a.run.app/sse",
      "headers": {
        "Authorization": "Bearer secret-bearer-token-for-user-123"
      }
    }
  }
}
```

## Operational Notes

### Cold Starts
Cloud Run scales to zero when unused. The first request after inactivity may take 5-10 seconds.
-   **Mitigation**: Run a "Keep Alive" pinger (e.g., Cloud Scheduler) hitting `/health` every 10 minutes for active users.

### Updates
To update the application logic:
1.  Re-run `./build.sh` to update the Golden Image.
2.  Re-run `provision_user.py` for each user. The script detects existing services and updates them to the new image revision.

### Troubleshooting
-   **Logs**: View logs in Google Cloud Console -> Cloud Run -> Logs.
-   **Health Check**: Visit `https://SERVICE_URL/health` to verify status.
    -   `200 OK`: Ready.
    -   `503 Service Unavailable`: Configuration missing or Vertex AI connection failed.
