# Decision: Agent Engine Provisioning Strategy

**Date**: 2025-12-11
**Decision Maker**: Planning session with Opus-4.5
**Status**: APPROVED for MVP

---

## Context

The OpenReflect MCP server requires a Vertex AI Agent Engine with Memory Bank to function. There are two approaches to provisioning this resource:

1. **Dynamic**: Create Agent Engine on first use via the `initialize_memory_bank` MCP tool
2. **Pre-Provisioned**: Create Agent Engine beforehand and pass `AGENT_ENGINE_NAME` as environment variable

This decision documents the trade-offs and chosen approach.

---

## Problem Statement

Recent modifications to the codebase created a conflict:

| Component | Original Design | Recent Modification |
|-----------|-----------------|---------------------|
| `config.py` | `is_valid()` = project_id only | `is_valid()` = project_id AND agent_engine_name |
| `server.py` | Load engine on first tool call | Load engine on startup from env |
| `/health` | 200 if HTTP server running | 503 if no Agent Engine |

**Impact**: The modifications broke the original "self-service" design where ChatGPT could call `initialize_memory_bank` to create the Agent Engine.

---

## Options Evaluated

### Option A: Dynamic Provisioning (Original Design)

**Description**: Server starts without Agent Engine. ChatGPT calls `initialize_memory_bank` tool which creates the Agent Engine.

```
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ChatGPT     │────▶│  MCP Server     │────▶│  Vertex AI      │
│               │     │  (no engine)    │     │                 │
│               │     │                 │     │                 │
│  calls tool:  │────▶│  creates engine │────▶│  Agent Engine   │
│  initialize   │     │  stores in app  │     │  now exists     │
└───────────────┘     └─────────────────┘     └─────────────────┘
```

| Pros | Cons |
|------|------|
| Self-service (no pre-setup) | First-call latency (~10-30s) |
| Works with any GCP project | `/health` complexity |
| No external tooling needed | Cold start + engine creation = slow |
| ChatGPT can customize memory topics | Harder to share engine across deploys |

### Option B: Pre-Provisioned

**Description**: Create Agent Engine via script/console before deployment. Pass resource name as `AGENT_ENGINE_NAME`.

```
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Setup       │────▶│  Vertex AI      │     │                 │
│   Script      │     │  Agent Engine   │     │                 │
│               │     │  (created)      │     │                 │
└───────────────┘     └────────┬────────┘     │                 │
                               │              │                 │
┌───────────────┐     ┌────────▼────────┐     │                 │
│   ChatGPT     │────▶│  MCP Server     │────▶│  (uses existing)│
│               │     │  AGENT_ENGINE=..│     │                 │
└───────────────┘     └─────────────────┘     └─────────────────┘
```

| Pros | Cons |
|------|------|
| Instant startup | Requires pre-setup step |
| Simple `/health` logic | Extra tooling to maintain |
| Engine survives redeploys | Harder for multi-user scenarios |
| Predictable behavior | Less flexible |

---

## Decision

**For MVP: Support Both Approaches**

The server should work with either approach, defaulting to dynamic provisioning for simplicity.

### Priority Order

1. **If `AGENT_ENGINE_NAME` is set** → Use pre-provisioned engine (fast startup)
2. **If `AGENT_ENGINE_NAME` is not set** → Allow `initialize_memory_bank` to create one (self-service)

---

## Implementation Details

### 1. Health Check Fix

`/health` must return 200 even without an Agent Engine, otherwise Cloud Run won't route traffic.

**Current (broken)**:
```python
@fastapi_app.get("/health")
async def health():
    if not app.is_ready():  # Requires Agent Engine!
        return Response(status_code=503)  # ❌ Blocks traffic
```

**Fixed**:
```python
@fastapi_app.get("/health")
async def health():
    return {
        "status": "ok",
        "initialized": app.is_ready(),
        "has_agent_engine": app.agent_engine is not None,
        "message": "Use initialize_memory_bank to complete setup" if not app.is_ready() else "Ready"
    }
```

### 2. Config Validation Fix

`is_valid()` should not require `AGENT_ENGINE_NAME`.

**Current (restrictive)**:
```python
def is_valid(self) -> bool:
    has_auth = bool(self.project_id or self.api_key)
    has_engine = bool(self.agent_engine_name)
    return has_auth and has_engine  # ❌ Requires engine
```

**Fixed**:
```python
def is_valid(self) -> bool:
    # Valid if we can authenticate to GCP
    # Agent Engine can be created later via tool
    return bool(self.project_id or self.api_key)
```

### 3. Server Startup Logic

**Current flow (in `server.py`)**:
```python
if app.config.is_valid():
    app.client = vertexai.Client(...)
    if app.config.agent_engine_name:
        app.agent_engine = app.client.agent_engines.get(...)
    app.initialized = True
```

**This is correct** — it loads engine if available, otherwise waits for `initialize_memory_bank`.

---

## Connection Flow (With Fix)

```
ChatGPT                          MCP Server                    Vertex AI
   │                                  │                            │
   │──── GET /sse ───────────────────▶│                            │
   │◀─── event: endpoint ────────────│                            │
   │                                  │                            │
   │──── POST /message {initialize} ─▶│                            │
   │◀─── {capabilities, tools} ──────│                            │
   │                                  │                            │
   │  (Option A: no engine yet)       │                            │
   │──── POST /message                │                            │
   │     {call: initialize_memory_bank}│───── create engine ───────▶│
   │◀─── {agent_engine: "..."}────────│◀──── engine created ───────│
   │                                  │                            │
   │  (Option B: engine pre-set)      │                            │
   │──── POST /message                │                            │
   │     {call: create_memory}────────│───── use existing ─────────▶│
   │◀─── {memory: {...}}──────────────│◀──── memory stored ────────│
```

---

## Environment Variables

### Dynamic Provisioning (Option A)

```bash
GOOGLE_CLOUD_PROJECT=directed-asset-479716-f6
GOOGLE_CLOUD_LOCATION=us-central1
# AGENT_ENGINE_NAME is NOT set - will be created via tool
```

### Pre-Provisioned (Option B)

```bash
GOOGLE_CLOUD_PROJECT=directed-asset-479716-f6
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_ENGINE_NAME=projects/directed-asset-479716-f6/locations/us-central1/reasoningEngines/123456
```

---

## Provisioning Script (For Option B)

For users who prefer pre-provisioning, a standalone script:

**File**: `mcp-server-python/scripts/create_agent_engine.py`

```python
#!/usr/bin/env python3
"""Create a Vertex AI Agent Engine with Memory Bank."""

import os
import vertexai

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "directed-asset-479716-f6")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

MEMORY_TOPICS = [
    "USER_PREFERENCES",
    "USER_PERSONAL_INFO",
    "KEY_CONVERSATION_DETAILS",
    "EXPLICIT_INSTRUCTIONS",
]

def main():
    print(f"Creating Agent Engine in {PROJECT_ID}/{LOCATION}...")
    
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    
    config = {
        "context_spec": {
            "memory_bank_config": {
                "customization_configs": [{
                    "memory_topics": [
                        {"managed_memory_topic": {"managed_topic_enum": topic}}
                        for topic in MEMORY_TOPICS
                    ]
                }]
            }
        }
    }
    
    agent_engine = client.agent_engines.create(config=config)
    name = agent_engine.api_resource.name
    
    print(f"\n✅ Agent Engine created!")
    print(f"\nAdd to your .env or Cloud Run config:")
    print(f"AGENT_ENGINE_NAME={name}")

if __name__ == "__main__":
    main()
```

**Usage**:
```bash
pip install vertexai google-cloud-aiplatform
gcloud auth application-default login
python scripts/create_agent_engine.py
```

---

## Validation Checklist

### Option A (Dynamic)

- [ ] Deploy without `AGENT_ENGINE_NAME`
- [ ] `/health` returns 200 (not 503)
- [ ] SSE connection works
- [ ] `initialize_memory_bank` tool is listed
- [ ] Calling `initialize_memory_bank` creates engine
- [ ] Memory tools work after initialization

### Option B (Pre-Provisioned)

- [ ] Run `create_agent_engine.py` script
- [ ] Deploy with `AGENT_ENGINE_NAME` set
- [ ] `/health` returns 200 with `initialized: true`
- [ ] Memory tools work immediately

---

## Risk Assessment

| Approach | Risk | Mitigation |
|----------|------|------------|
| Dynamic | First-call is slow | Document expected latency |
| Dynamic | Engine creation might fail | Clear error messages |
| Pre-Provisioned | Requires extra step | Provide simple script |
| Pre-Provisioned | Engine must exist | Script validates on run |

---

## Files To Modify

1. **`mcp-server-python/src/config.py`**: Remove `has_engine` from `is_valid()`
2. **`mcp-server-python/src/server_http.py`**: Fix `/health` to always return 200
3. **`mcp-server-python/scripts/create_agent_engine.py`**: New file for Option B users

**Estimated Changes**: ~20 lines across 2 existing files + 1 new script

---

## Approval

**Decision**: Support both dynamic and pre-provisioned approaches

**Rationale**:
1. Dynamic is more user-friendly for getting started
2. Pre-provisioned is better for production/repeated deploys
3. Both can coexist with minimal code changes

**Next Steps**:
1. Fix `/health` endpoint to return 200 always
2. Update `is_valid()` to not require `AGENT_ENGINE_NAME`
3. Create provisioning script for Option B users
4. Update documentation with both approaches

---

## References

- `agent-collab/decisions/opus-45-auth-strategy-120925-2030.md`
- `agent-collab/reviews/opus-45-auth-conflict-review-121025.md`
- `mcp-server-python/src/tools.py` (lines 29-116)

