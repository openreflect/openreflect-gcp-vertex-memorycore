# Tier 3: Per-User Cloud Run Services

**Status**: Advanced / Future Use  
**Current Strategy**: Tier 1 (Shared Engine with Scope Isolation)

---

## What Is This?

This folder contains scripts for provisioning **per-user Cloud Run services** (Tier 3 isolation). This approach was considered during early architecture design but is **not the current deployment strategy**.

## Current Architecture (Tier 1)

OpenReflect currently uses **Tier 1 isolation**:
- Single Cloud Run service for all users
- Single Vertex AI Agent Engine
- User isolation via `scope` parameter
- See [ARCHITECTURE_STRATEGY.md](../../../docs/ARCHITECTURE_STRATEGY.md)

## When Would Tier 3 Be Used?

Tier 3 (per-user services) might be appropriate for:

| Use Case | Why |
|----------|-----|
| Enterprise compliance | Customer requires dedicated infrastructure |
| Data residency | Customer data must stay in specific region |
| Resource isolation | Customer needs guaranteed compute resources |
| Premium tier | Offering isolated service as upsell |

## Files

| File | Purpose |
|------|---------|
| `provision_user.py` | Script to create a dedicated Cloud Run service per user |

## Usage (If Needed)

```bash
# Only use if Tier 3 isolation is required
python provision_user.py --user-id <user_id> --project <gcp_project>
```

## Warning

Using Tier 3 significantly increases:
- Infrastructure complexity
- Operational cost (per-user Cloud Run services)
- Deployment overhead

For most use cases, **Tier 1 (scope-based isolation) is recommended**.
