---
name: Phase 0 Memory Bank Implementation Checklist
overview: Deploy the Vertex AI Memory Bank MCP server as a containerized HTTP service on Google Cloud Run, enabling remote MCP client access via HTTP transport.
todos:
  - id: todo-1764547030842-8l8zpyo7m
    content: ""
    status: pending
---

# Deploy Vertex AI Memory Bank MCP Server to Google Cloud Run

## Overview

Deploy the Vertex AI Memory Bank MCP server (`MCP/source-120125/vertex-memory-bank-mcp-main`) as a containerized HTTP service on Google Cloud Run, enabling remote MCP clients to access Memory Bank functionality via HTTP transport.

## Architecture

- **Container**: Python 3.11+ application running FastMCP server in HTTP mode
- **Transport**: MCP HTTP transport (similar to Firecrawl MCP streamableHttpMode)
- **Authentication**: Google Cloud service account with Vertex AI permissions
- **Deployment**: Cloud Run service with environment variable configuration

## Prerequisites

- Google Cloud project: `directed-asset-479716-f6`
- Vertex AI API enabled
- Service account with `aiplatform.user` role
- Docker installed locally (for building)
- gcloud CLI configured

## Implementation Steps

### 1. Create Dockerfile

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/Dockerfile`

- Use Python 3.11 slim base image
- Set working directory
- Copy requirements and install dependencies from `requirements.txt`
- Copy application source code (`src/`, `memory_bank_server.py`)
- Expose port 8080 (Cloud Run default)
- Set entrypoint to run MCP server in HTTP mode
- Configure logging to stdout/stderr appropriately

### 2. Modify Server for HTTP Mode

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/src/server.py`

- Add HTTP server capability to FastMCP (check if FastMCP supports HTTP transport)
- If not supported natively, wrap with HTTP server (e.g., using `mcp.server.stdio` with HTTP adapter or custom HTTP handler)
- Configure server to listen on `PORT` environment variable (Cloud Run provides this)
- Ensure MCP protocol works over HTTP (may need to use SSE or WebSocket transport)

### 3. Create Cloud Run Deployment Configuration

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/cloud-run.yaml` (optional, for gcloud deployment)

- Service name: `vertex-memory-bank-mcp`
- Region: `us-central1` (matching Vertex AI location)
- Port: 8080
- Environment variables:
- `GOOGLE_CLOUD_PROJECT`: `directed-asset-479716-f6`
- `GOOGLE_CLOUD_LOCATION`: `us-central1`
- `PORT`: `8080` (Cloud Run sets this automatically)
- Optional: `AGENT_ENGINE_NAME` if reusing existing engine
- Service account: Create/use service account with Vertex AI permissions
- CPU: 1 vCPU (minimum)
- Memory: 512Mi (minimum, may need more)
- Max instances: 10 (adjust based on usage)
- Timeout: 300s (for long-running memory operations)

### 4. Create Build Script

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/build-and-deploy.sh`

- Build Docker image using Cloud Build or local Docker
- Tag image: `gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest`
- Push to Google Container Registry or Artifact Registry
- Deploy to Cloud Run using `gcloud run deploy`

### 5. Configure Service Account Permissions

**Actions**:

- Create service account: `vertex-memory-bank-mcp-sa`
- Grant roles:
- `roles/aiplatform.user` (for Vertex AI Memory Bank access)
- `roles/run.invoker` (if using Cloud Run authentication)
- Create and download service account key (if needed for local testing)
- Configure Cloud Run service to use this service account

### 6. Update Configuration for Cloud Run

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/src/config.py`

- Ensure environment variable reading works in containerized environment
- Remove `.env` file dependency (Cloud Run uses environment variables)
- Verify `GOOGLE_APPLICATION_CREDENTIALS` handling (Cloud Run provides credentials automatically via metadata service)

### 7. Add Health Check Endpoint

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/src/server.py`

- Add `/health` endpoint for Cloud Run health checks
- Return 200 OK when server is initialized and ready
- Return 503 if not ready (Vertex AI client not initialized)

### 8. Create Deployment Documentation

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/DEPLOYMENT.md`

- Document deployment steps
- Include gcloud commands for deployment
- Document environment variables
- Include troubleshooting guide
- Document MCP client configuration for HTTP mode

### 9. Test Deployment

**Actions**:

- Build and push Docker image
- Deploy to Cloud Run
- Verify service is running and healthy
- Test MCP client connection via HTTP
- Verify Memory Bank operations (initialize, generate, retrieve)

### 10. Configure MCP Client Access

**File**: `MCP/source-120125/vertex-memory-bank-mcp-main/examples/cloud-run-client-config.json`

- Example MCP client configuration for HTTP transport
- Include Cloud Run service URL
- Document authentication (API key or service account)
- Include example using Cursor MCP configuration

## Technical Considerations

### MCP HTTP Transport

- FastMCP may need HTTP adapter or custom HTTP handler
- Consider using MCP's HTTP transport specification
- May need to implement SSE (Server-Sent Events) or WebSocket for streaming
- Ensure MCP protocol messages are properly serialized over HTTP

### Authentication

- Cloud Run service account provides automatic authentication to Vertex AI
- For external MCP clients, may need API key or IAM-based authentication
- Consider Cloud Run's built-in authentication mechanisms

### Resource Requirements

- Memory Bank operations can be memory-intensive
- Consider 1GB+ memory allocation
- CPU may need to scale based on concurrent requests

### Environment Variables

- `GOOGLE_CLOUD_PROJECT`: Required
- `GOOGLE_CLOUD_LOCATION`: Required (default: us-central1)
- `AGENT_ENGINE_NAME`: Optional (reuse existing engine)
- `PORT`: Cloud Run sets automatically

## Files to Create/Modify

1. **Create**: `MCP/source-120125/vertex-memory-bank-mcp-main/Dockerfile`
2. **Modify**: `MCP/source-120125/vertex-memory-bank-mcp-main/src/server.py` (add HTTP server support)
3. **Create**: `MCP/source-120125/vertex-memory-bank-mcp-main/cloud-run.yaml` (deployment config)
4. **Create**: `MCP/source-120125/vertex-memory-bank-mcp-main/build-and-deploy.sh` (deployment script)
5. **Create**: `MCP/source-120125/vertex-memory-bank-mcp-main/DEPLOYMENT.md` (documentation)
6. **Create**: `MCP/source-120125/vertex-memory-bank-mcp-main/examples/cloud-run-client-config.json` (client config example)

## Implementation Checklist

- [ ] **dockerfile-setup**: Create Dockerfile with Python 3.11 base image, install dependencies, configure entrypoint
- [ ] **http-server-modification**: Modify server.py to support HTTP transport mode for MCP protocol
- [ ] **cloud-run-config**: Create cloud-run.yaml deployment configuration file
- [ ] **build-script**: Create build-and-deploy.sh script for automated deployment
- [ ] **service-account-setup**: Create service account and configure IAM permissions
- [ ] **config-cloud-run**: Update config.py to work properly in containerized Cloud Run environment
- [ ] **health-endpoint**: Add /health endpoint to server.py for Cloud Run health checks
- [ ] **deployment-docs**: Create DEPLOYMENT.md with deployment instructions and troubleshooting
- [ ] **client-config-example**: Create cloud-run-client-config.json example for MCP clients
- [ ] **local-testing**: Test Docker container locally before Cloud Run deployment
- [ ] **cloud-run-deploy**: Deploy service to Cloud Run and verify deployment
- [ ] **integration-testing**: Test MCP client connection and Memory Bank operations end-to-end
- [ ] **monitoring-setup**: Configure Cloud Run logging and monitoring for the service
- [ ] **security-review**: Review and verify service account permissions and security settings
- [ ] **documentation-update**: Update README.md with Cloud Run deployment information

## Verification Steps

1. Docker image builds successfully
2. Container runs locally and responds to HTTP requests
3. Cloud Run service deploys without errors
4. Health check endpoint returns 200 OK
5. MCP client can connect via HTTP
6. Memory Bank operations (initialize, generate, retrieve) work correctly
7. Service account has correct permissions
8. Logs show successful Vertex AI client initializati