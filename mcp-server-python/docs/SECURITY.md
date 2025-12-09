# Security Review Checklist for Vertex AI Memory Bank MCP Server

This document provides a comprehensive security review checklist for the Cloud Run deployment.

## Service Account Permissions

### ✅ Required Permissions

Verify the service account has only the minimum required permissions:

```bash
# Check current IAM bindings
gcloud projects get-iam-policy directed-asset-479716-f6 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

**Required Roles:**
- ✅ `roles/aiplatform.user` - For Vertex AI Memory Bank access
- ✅ `roles/run.invoker` - Only if using Cloud Run authentication

**Should NOT Have:**
- ❌ `roles/owner` or `roles/editor` - Too permissive
- ❌ `roles/aiplatform.admin` - Unnecessary admin access
- ❌ Storage or other unrelated permissions

### Verification Commands

```bash
# List all roles for the service account
gcloud projects get-iam-policy directed-asset-479716-f6 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com"

# Test Vertex AI access
gcloud ai-platform models list \
  --region=us-central1 \
  --project=directed-asset-479716-f6 \
  --impersonate-service-account=vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com
```

## Network Security

### ✅ Cloud Run Configuration

**Current Configuration:**
- ✅ Service is publicly accessible (if using `--allow-unauthenticated`)
- ⚠️ Consider VPC connector for private access in production
- ✅ HTTPS enforced (Cloud Run default)

**Recommendations:**
1. **Use VPC Connector** for private access:
   ```bash
   gcloud run services update vertex-memory-bank-mcp \
     --vpc-connector=CONNECTOR_NAME \
     --vpc-egress=private-ranges-only \
     --region us-central1 \
     --project directed-asset-479716-f6
   ```

2. **Enable Authentication** for production:
   ```bash
   gcloud run services update vertex-memory-bank-mcp \
     --no-allow-unauthenticated \
     --region us-central1 \
     --project directed-asset-479716-f6
   ```

3. **Restrict Ingress** to specific sources if needed:
   ```bash
   gcloud run services update vertex-memory-bank-mcp \
     --ingress=internal \
     --region us-central1 \
     --project directed-asset-479716-f6
   ```

## Authentication & Authorization

### ✅ Current Setup

- ✅ Service account authentication for Vertex AI (automatic via metadata service)
- ⚠️ No authentication required for HTTP endpoints (if `--allow-unauthenticated`)
- ✅ No API keys stored in code or environment variables

### Recommendations

1. **Add API Key Authentication** (if needed):
   ```python
   # In server_http.py
   API_KEY = os.getenv("API_KEY")
   
   @fastapi_app.middleware("http")
   async def verify_api_key(request: Request, call_next):
       if request.url.path not in ["/health", "/"]:
           api_key = request.headers.get("X-API-Key")
           if api_key != API_KEY:
               return Response(status_code=401)
       return await call_next(request)
   ```

2. **Use Cloud IAM** for authentication:
   ```bash
   # Require authentication
   gcloud run services update vertex-memory-bank-mcp \
     --no-allow-unauthenticated \
     --region us-central1 \
     --project directed-asset-479716-f6
   ```

3. **Use Identity-Aware Proxy (IAP)** for additional security layer

## Secrets Management

### ✅ Current Implementation

- ✅ No secrets hardcoded in code
- ✅ Environment variables used for configuration
- ⚠️ Consider Secret Manager for sensitive values

### Recommendations

1. **Use Secret Manager** for sensitive configuration:
   ```bash
   # Create secret
   echo -n "sensitive-value" | gcloud secrets create api-key \
     --data-file=- \
     --project directed-asset-479716-f6
   
   # Grant access to service account
   gcloud secrets add-iam-policy-binding api-key \
     --member="serviceAccount:vertex-memory-bank-mcp-sa@directed-asset-479716-f6.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor" \
     --project directed-asset-479716-f6
   
   # Mount secret in Cloud Run
   gcloud run services update vertex-memory-bank-mcp \
     --update-secrets API_KEY=api-key:latest \
     --region us-central1 \
     --project directed-asset-479716-f6
   ```

## Container Security

### ✅ Dockerfile Security

**Current Implementation:**
- ✅ Uses official Python slim image
- ✅ Runs as non-root user (Cloud Run default)
- ✅ Minimal dependencies
- ✅ No unnecessary packages

**Recommendations:**
1. **Scan images for vulnerabilities**:
   ```bash
   gcloud container images scan gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest
   ```

2. **Use distroless images** for better security:
   ```dockerfile
   FROM gcr.io/distroless/python3-debian11
   ```

3. **Keep dependencies updated**:
   ```bash
   pip list --outdated
   pip install --upgrade package-name
   ```

## Data Security

### ✅ Memory Bank Data

- ✅ Data stored in Vertex AI Memory Bank (encrypted at rest)
- ✅ Data scoped by user_id (isolation)
- ✅ No data stored in container or logs
- ✅ No PII logged (verify logging statements)

### Recommendations

1. **Review logging** to ensure no sensitive data:
   ```bash
   # Check logs for sensitive data
   gcloud logging read "resource.type=cloud_run_revision AND \
     resource.labels.service_name=vertex-memory-bank-mcp" \
     --limit 100 \
     --format json \
     --project directed-asset-479716-f6 | grep -i "password\|token\|key\|secret"
   ```

2. **Enable audit logs** for Vertex AI operations:
   ```bash
   gcloud logging sinks create vertex-ai-audit \
     bigquery.googleapis.com/projects/directed-asset-479716-f6/datasets/audit_logs \
     --log-filter='resource.type="aiplatform.googleapis.com/Model" OR \
       resource.type="aiplatform.googleapis.com/Endpoint"' \
     --project directed-asset-479716-f6
   ```

## Input Validation

### ✅ Current Implementation

- ✅ Input validation in `src/validators.py`
- ✅ Pydantic models for type validation
- ✅ Error handling for invalid inputs

### Verification

Review validation functions:
- `validate_scope()` - Validates user_id format
- `validate_conversation()` - Validates conversation input
- `validate_memory_fact()` - Validates memory fact format

## Rate Limiting

### ⚠️ Current Status

- ⚠️ No rate limiting implemented
- ✅ Cloud Run has built-in request limits
- ⚠️ Consider adding application-level rate limiting

### Recommendations

1. **Use Cloud Armor** for DDoS protection:
   ```bash
   gcloud compute security-policies create mcp-security-policy \
     --project directed-asset-479716-f6
   ```

2. **Implement rate limiting** in application:
   ```python
   from slowapi import Limiter, _rate_limit_exceeded_handler
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   fastapi_app.state.limiter = limiter
   fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
   
   @fastapi_app.post("/sse")
   @limiter.limit("10/minute")
   async def sse_endpoint(request: Request):
       # ...
   ```

## Compliance & Auditing

### ✅ Checklist

- ✅ Service account follows least-privilege principle
- ✅ No hardcoded credentials
- ✅ Environment variables for configuration
- ✅ Logging enabled for audit trail
- ⚠️ Consider enabling Cloud Audit Logs
- ⚠️ Document data retention policies

### Enable Audit Logs

```bash
# Enable Data Access audit logs
gcloud logging sinks create data-access-audit \
  bigquery.googleapis.com/projects/directed-asset-479716-f6/datasets/audit_logs \
  --log-filter='protoPayload.serviceName="aiplatform.googleapis.com"' \
  --project directed-asset-479716-f6
```

## Security Testing

### ✅ Testing Checklist

1. **Penetration Testing**:
   - [ ] Test for SQL injection (N/A - no SQL)
   - [ ] Test for XSS (verify input sanitization)
   - [ ] Test for CSRF (verify token validation)
   - [ ] Test authentication bypass
   - [ ] Test authorization checks

2. **Dependency Scanning**:
   ```bash
   pip install safety
   safety check
   ```

3. **Container Scanning**:
   ```bash
   gcloud container images scan gcr.io/directed-asset-479716-f6/vertex-memory-bank-mcp:latest
   ```

## Incident Response

### ✅ Preparedness

- ✅ Monitoring and alerting configured
- ✅ Logging enabled
- ⚠️ Document incident response procedures
- ⚠️ Define escalation paths

### Recommendations

1. **Create runbook** for common security incidents
2. **Set up security alerts** for:
   - Unusual API access patterns
   - Failed authentication attempts
   - Unauthorized service account usage
3. **Regular security reviews** (quarterly recommended)

## Summary

### ✅ Security Strengths

- Service account follows least-privilege
- No hardcoded secrets
- Input validation implemented
- HTTPS enforced
- Data encrypted at rest (Vertex AI)

### ⚠️ Areas for Improvement

1. Add authentication for HTTP endpoints (production)
2. Use Secret Manager for sensitive values
3. Implement rate limiting
4. Enable Cloud Audit Logs
5. Regular dependency updates
6. Container vulnerability scanning

### 🔒 Production Readiness

Before production deployment, ensure:
- [ ] Authentication enabled
- [ ] Rate limiting implemented
- [ ] Audit logs enabled
- [ ] Security alerts configured
- [ ] Incident response plan documented
- [ ] Regular security reviews scheduled
