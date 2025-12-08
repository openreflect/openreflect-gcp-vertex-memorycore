# Deployment Guide: Vertex AI Memory Bank MCP Server to Google Cloud Run

This guide walks you through deploying the Vertex AI Memory Bank MCP server to Google Cloud Run.

## Prerequisites

- Google Cloud project: `directed-asset-479716-f6`
- Vertex AI API enabled
- Docker installed locally (for building)
- gcloud CLI configured and authenticated
- Service account with appropriate permissions

## Step 1: Create Service Account

Create a service account for the Cloud Run service:

```bash
gcloud iam service-accounts create vertex-memory-bank-mcp-sa \
  --display-name="Vertex Memory Bank MCP Service Account" \
  --project=directed-asset-479716-f6
```

## Step 2: Grant Permissions

Grant the necessary IAM roles to the service account:

```bash
# Grant Vertex AI access
gcloud projects add-iam-policy-binding directed-asset-479716-f6 \
  --member="serviceAccount:vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Grant Cloud Run invoker access (if needed for authentication)
gcloud projects add-iam-policy-binding directed-asset-479716-f6 \
  --member="serviceAccount:vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

## Step 3: Enable Required APIs

Ensure the following APIs are enabled:

```bash
gcloud services enable aiplatform.googleapis.com --project=directed-asset-479716-f6
gcloud services enable run.googleapis.com --project=directed-asset-479716-f6
gcloud services enable containerregistry.googleapis.com --project=directed-asset-479716-f6
```

## Step 4: Build and Deploy

### Option A: Using the Build Script

```bash
cd MCP/source-120125/vertex-memory-bank-mcp-main
chmod +x build-and-deploy.sh
./build-and-deploy.sh
```

### Option B: Manual Deployment

```bash
# Set variables
PROJECT_ID="directed-asset-479716-f6"
REGION="us-central1"
SERVICE_NAME="vertex-memory-bank-mcp"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

# Build Docker image
docker build -t ${IMAGE_NAME} .

# Push to Google Container Registry
docker push ${IMAGE_NAME}

# Deploy to Cloud Run
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --service-account vertex-memory-bank-mcp-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION} \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300s \
  --max-instances 10 \
  --port 8080
```

## Step 5: Verify Deployment

Check the service status:

```bash
gcloud run services describe vertex-memory-bank-mcp \
  --region us-central1 \
  --project directed-asset-479716-f6 \
  --format 'value(status.url)'
```

Test the health endpoint:

```bash
SERVICE_URL=$(gcloud run services describe vertex-memory-bank-mcp \
  --region us-central1 \
  --project directed-asset-479716-f6 \
  --format 'value(status.url)')

curl ${SERVICE_URL}/health
```

## Environment Variables

The following environment variables are configured automatically:

- `PORT`: Set to 8080 by Cloud Run
- `GOOGLE_CLOUD_PROJECT`: `directed-asset-479716-f6`
- `GOOGLE_CLOUD_LOCATION`: `us-central1`
- `AGENT_ENGINE_NAME`: Optional (can be set to reuse existing engine)
- `CONNECTOR_BEARER_TOKEN`: Optional bearer token enforced by HTTPS/SSE endpoints for external connectors

## MCP Client Configuration

See `examples/cloud-run-client-config.json` for MCP client configuration examples.

### Cursor MCP Configuration

Add to your `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "vertex-memory-bank": {
      "url": "https://vertex-memory-bank-mcp-xxxxx-uc.a.run.app/mcp/stream",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

Replace `YOUR_TOKEN` with `CONNECTOR_BEARER_TOKEN` if authentication is enabled. The legacy `/sse` path remains available; `/mcp/stream` is recommended for ChatGPT/connector SSE.

### Manifest Endpoint

For connector discovery, the service exposes `/manifest` with basic metadata and listed tools/resources. Example:

```bash
curl https://vertex-memory-bank-mcp-xxxxx-uc.a.run.app/manifest
```

## Troubleshooting

### Service Won't Start

1. Check Cloud Run logs:
   ```bash
   gcloud run services logs read vertex-memory-bank-mcp \
     --region us-central1 \
     --project directed-asset-479716-f6
   ```

2. Verify service account permissions:
   ```bash
   gcloud projects get-iam-policy directed-asset-479716-f6 \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com"
   ```

### Health Check Failing

- Verify Vertex AI API is enabled
- Check that environment variables are set correctly
- Ensure the service account has `roles/aiplatform.user` permission

### Memory Bank Operations Failing

- Verify the service account has access to Vertex AI Memory Bank
- Check that the project ID and location are correct
- Review Cloud Run logs for detailed error messages

### Connection Issues

- Verify the service URL is correct
- Check firewall rules if accessing from outside GCP
- If `CONNECTOR_BEARER_TOKEN` is set, include `Authorization: Bearer <token>`
- Ensure the service is not restricted to authenticated users only (if using `--allow-unauthenticated`)

## Resource Limits

Current configuration:
- **CPU**: 1 vCPU
- **Memory**: 1Gi (512Mi minimum, 1Gi limit)
- **Timeout**: 300 seconds
- **Max Instances**: 10
- **Concurrency**: 80 requests per instance

Adjust these based on your workload requirements.

## Monitoring

View logs in Cloud Console:
```bash
gcloud run services logs read vertex-memory-bank-mcp \
  --region us-central1 \
  --project directed-asset-479716-f6 \
  --limit 50
```

Set up alerts in Cloud Monitoring for:
- Request latency
- Error rates
- Memory usage
- CPU utilization

## Security Considerations

1. **Service Account**: Uses least-privilege IAM roles
2. **Authentication**: Currently allows unauthenticated access. Consider adding authentication for production.
   - Set `CONNECTOR_BEARER_TOKEN` to require a bearer token at the HTTPS/SSE layer (separate from GCP IAM)
3. **Network**: Service is publicly accessible. Consider VPC connector for private access.
4. **Secrets**: Use Secret Manager for sensitive configuration if needed.

## Updating the Service

To update the service with a new image:

```bash
./build-and-deploy.sh
```

Or manually:

```bash
docker build -t gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest .
docker push gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest
gcloud run deploy vertex-memory-bank-mcp \
  --image gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest \
  --region us-central1 \
  --project directed-asset-479716-f6
```

## Rollback

To rollback to a previous revision:

```bash
# List revisions
gcloud run revisions list \
  --service vertex-memory-bank-mcp \
  --region us-central1 \
  --project directed-asset-479716-f6

# Rollback to specific revision
gcloud run services update-traffic vertex-memory-bank-mcp \
  --to-revisions REVISION_NAME=100 \
  --region us-central1 \
  --project directed-asset-479716-f6
```

