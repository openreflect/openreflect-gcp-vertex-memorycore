# Decision: MVP Authentication Strategy for ChatGPT Web MCP

**Date**: 2025-12-09
**Decision Maker**: Planning session with Opus-4.5
**Status**: APPROVED for MVP

---

## Context

OpenReflect MCP server needs to connect to OpenAI's ChatGPT web interface. The server will be hosted on Google Cloud Run and must authenticate:
1. **Inbound**: ChatGPT → MCP Server (who can call our endpoints)
2. **Outbound**: MCP Server → Vertex AI (how we access GCP services)

## Constraint Discovery

Analysis of the ChatGPT "New App" MCP configuration interface revealed:

| Auth Option | Available |
|-------------|-----------|
| OAuth (Client ID + Secret) | ✅ Yes |
| No Auth | ✅ Yes |
| Bearer Token | ❌ **Not available** |
| API Key | ❌ Not available |

**Critical Finding**: The original implementation's `CONNECTOR_BEARER_TOKEN` approach is **incompatible** with ChatGPT's interface. ChatGPT only offers OAuth or No Auth.

---

## Options Evaluated

### Option 1: No Auth (Selected for MVP)

**Description**: Allow unauthenticated access to the MCP server endpoints.

| Pros | Cons |
|------|------|
| Zero implementation effort | Anyone with URL can access |
| Fastest path to testing | No audit trail of who accessed |
| Works immediately with ChatGPT | Must secure via other means |

**Risk Mitigation**:
- Use for internal testing only
- Don't store sensitive data during MVP
- Delete/redeploy after testing phase
- Consider Cloud Run IAM for additional layer

### Option 2: OAuth 2.0 Stub

**Description**: Implement minimal OAuth endpoints that accept hardcoded credentials.

| Pros | Cons |
|------|------|
| Satisfies ChatGPT's OAuth requirement | Still fake security |
| Looks "proper" | Additional code to write |
| Can evolve to real OAuth | Complexity for no real benefit |

**Verdict**: Unnecessary complexity for MVP.

### Option 3: Full OAuth 2.0

**Description**: Implement proper OAuth 2.0 authorization code flow.

| Pros | Cons |
|------|------|
| Production-ready security | Significant implementation time |
| Industry standard | Requires token storage/management |
| Proper access control | Overkill for MVP testing |

**Verdict**: Post-MVP enhancement.

---

## Decision

**For MVP: Use No Auth**

### Rationale

1. **Speed to Value**: Need to validate the MCP ↔ ChatGPT ↔ Vertex AI integration works before investing in auth infrastructure
2. **Interface Constraint**: ChatGPT doesn't support our original bearer token approach
3. **Acceptable Risk**: For internal testing with non-sensitive data, open access is tolerable
4. **Easy Upgrade Path**: Can add OAuth later without changing core MCP functionality

---

## Implementation Details

### Inbound Auth (ChatGPT → MCP Server)

**Configuration**: None required

**Code Status**: Already supported
```python
# server_http.py lines 76-83
def _authorize(request: Request) -> Optional[Response]:
    if not CONNECTOR_BEARER_TOKEN:
        pass  # Open access when token not configured
```

**Cloud Run Deployment**:
```bash
gcloud run deploy vertex-memory-bank-mcp \
  --allow-unauthenticated \
  # ... other flags
```

**ChatGPT Configuration**:
```
Name: Vertex Memory Bank
MCP Server URL: https://your-service.a.run.app/sse
Authentication: (None)
```

### Outbound Auth (MCP Server → Vertex AI)

**Approach**: GCP Service Account (attached to Cloud Run)

**Configuration**:
```bash
GOOGLE_CLOUD_PROJECT=directed-asset-479716-f6
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_ENGINE_NAME=projects/.../engines/your-engine
```

**Why Service Account over API Key**:
- Cloud Run automatically provides SA credentials
- No secrets to hardcode or leak
- Proper IAM role binding (`roles/aiplatform.user`)
- Works without code changes

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MVP Authentication Flow                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ChatGPT Web                                                            │
│  (OpenAI)                                                               │
│       │                                                                 │
│       │ NO AUTH                                                         │
│       │ URL: https://your-service.a.run.app/sse                        │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  Cloud Run                                                   │       │
│  │  - Allow unauthenticated: YES                               │       │
│  │  - Service Account attached                                  │       │
│  │                                                              │       │
│  │  MCP Server                                                  │       │
│  │  - /sse (SSE endpoint)                                      │       │
│  │  - /message (JSON-RPC)                                      │       │
│  │  - /health                                                   │       │
│  └─────────────────────────────────────────────────────────────┘       │
│       │                                                                 │
│       │ SERVICE ACCOUNT AUTH                                           │
│       │ (automatic via Cloud Run)                                      │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  Vertex AI Agent Engine                                      │       │
│  │  Memory Bank                                                 │       │
│  │  - roles/aiplatform.user granted to SA                      │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Environment Variables (MVP)

| Variable | Value | Required |
|----------|-------|----------|
| `GOOGLE_CLOUD_PROJECT` | `directed-asset-479716-f6` | ✅ Yes |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | ✅ Yes |
| `AGENT_ENGINE_NAME` | `projects/.../engines/...` | ✅ Yes |
| `CONNECTOR_BEARER_TOKEN` | *(do not set)* | ❌ No |

---

## Deployment Command

```bash
# Build image
cd mcp-server-python
./deploy/build.sh

# Deploy with no auth
gcloud run deploy vertex-memory-bank-mcp \
  --image gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --service-account vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=directed-asset-479716-f6" \
  --set-env-vars "GOOGLE_CLOUD_LOCATION=us-central1" \
  --set-env-vars "AGENT_ENGINE_NAME=projects/directed-asset-479716-f6/locations/us-central1/collections/default_collection/engines/YOUR_ENGINE"
```

---

## Validation Checklist

After deployment, verify:

- [ ] `/health` returns `200 OK` with `{"status": "healthy"}`
- [ ] `/sse` establishes SSE connection and sends endpoint event
- [ ] `/message` with `initialize` returns server capabilities
- [ ] ChatGPT can connect and list tools
- [ ] Memory tools work (create, retrieve, list)

---

## Security Acknowledgments

**Accepted Risks for MVP**:
1. Public URL is accessible to anyone
2. No authentication of callers
3. Rate limiting depends on Cloud Run defaults

**Mitigations**:
1. Use non-obvious service name
2. Monitor Cloud Run logs for unexpected access
3. Delete deployment after MVP validation
4. Do not store production/sensitive data

---

## Future Enhancements (Post-MVP)

| Priority | Enhancement | Effort |
|----------|-------------|--------|
| P1 | OAuth 2.0 implementation | Medium |
| P2 | Cloud Run IAM + Identity-Aware Proxy | Medium |
| P3 | Per-user token management | High |
| P4 | Audit logging | Low |

---

## Approval

**Decision**: Proceed with No Auth for MVP

**Next Steps**:
1. Ensure Vertex AI Agent Engine is provisioned
2. Create/verify service account with correct IAM roles
3. Build and deploy to Cloud Run
4. Configure ChatGPT with service URL
5. Test end-to-end memory operations

---

## References

- [OpenAI MCP Documentation](https://platform.openai.com/docs/mcp)
- `openreflect-implementation-plan-120925-1718.md`
- `openreflect-status-120925-1718.md`
- Session: `agent-collab/sessions/opus-45-collaborator-12925-1905.md`

