# OpenReflect — Vertex AI Memory Bank MCP Server

A proof-of-concept MCP server that gives ChatGPT persistent memory capabilities via Google Cloud's Vertex AI Memory Bank.

---

## 🧪 Project Status: Prototype / MVP

> This is an **experimental proof-of-concept** exploring how to:
> - Connect ChatGPT's web interface to external memory systems
> - Use the Model Context Protocol (MCP) for AI-to-service communication
> - Leverage Vertex AI Agent Engine for persistent memory storage

---

## What It Does

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   User ──► ChatGPT Web ──► MCP Server ──► Vertex AI Memory Bank    │
│                              (Cloud Run)      (Agent Engine)        │
│                                                                     │
│   "Remember that I prefer dark mode"                                │
│                    ↓                                                │
│   Memory stored: {"fact": "User prefers dark mode", ...}           │
│                    ↓                                                │
│   Next session: ChatGPT recalls the preference automatically       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Memory Capabilities

| Tool | Description |
|------|-------------|
| `initialize_memory_bank` | Connect to Vertex AI project |
| `generate_memories` | Extract memories from conversations |
| `retrieve_memories` | Fetch stored memories (with semantic search) |
| `create_memory` | Store a specific fact |
| `delete_memory` | Remove a memory |
| `list_memories` | View all stored memories |

---

## How It Works: SSE Connection Flow

```
ChatGPT Web                              MCP Server (Cloud Run)
     │                                          │
     │──── GET /sse ────────────────────────────▶│  1. SSE connection
     │◀─── event: endpoint ─────────────────────│     established
     │                                          │
     │──── POST /message {initialize} ──────────▶│  2. Protocol handshake
     │◀─── {capabilities, tools} ───────────────│     returns available tools
     │                                          │
     │──── POST /message {tools/list} ──────────▶│  3. Tool discovery
     │◀─── {initialize_memory_bank, ...} ───────│
     │                                          │
     │──── POST /message                        │  4. First-time setup
     │     {call: initialize_memory_bank} ──────▶│     creates Agent Engine
     │◀─── {agent_engine_name: "..."} ──────────│     (if not pre-provisioned)
     │                                          │
     │──── Memory operations ready ─────────────▶│  5. Store/retrieve memories
     │◀─── {memories: [...]} ───────────────────│
     │                                          │
```

**Key Points**:
- SSE transport works without pre-existing Agent Engine
- `initialize_memory_bank` can create the Agent Engine on first use
- Or, pre-provision Agent Engine and set `AGENT_ENGINE_NAME` for faster startup

---

## Target Stack (MVP)

| Component | Technology |
|-----------|------------|
| **Client** | ChatGPT web interface (OpenAI) |
| **Transport** | Server-Sent Events (SSE) + JSON-RPC |
| **Hosting** | Google Cloud Run |
| **Storage** | Vertex AI Agent Engine with Memory Bank |
| **Auth** | No authentication (MVP only) |

---

## Project Structure

```
openreflect-core/
├── mcp-server-python/          # Main MCP server implementation
│   ├── src/                    # Source code
│   ├── deploy/                 # Cloud Run deployment scripts
│   ├── docs/                   # Technical documentation
│   └── Dockerfile              # Container definition
│
├── agent-collab/               # AI-assisted development archive
│   ├── sessions/               # AI session summaries
│   ├── decisions/              # Architecture decisions
│   └── reviews/                # Code and security reviews
│
└── docs/                       # Reference documentation
    └── origin/                 # External API specs
```

---
## Getting Started

### Prerequisites

- Google Cloud account with Vertex AI API enabled
- Python 3.11+
- Docker (for Cloud Run deployment)
- gcloud CLI configured

### Quick Start

```bash
# 1. Clone and navigate
cd mcp-server-python

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export AGENT_ENGINE_NAME=projects/.../engines/your-engine

# 4. Run locally
python -m uvicorn src.server_http:app --port 8080
```

### Deploy to Cloud Run

```bash
cd mcp-server-python
./deploy/build.sh

gcloud run deploy openreflect-mcp \
  --image gcr.io/$PROJECT_ID/openreflect-mcp:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --timeout 3600
```

See `mcp-server-python/docs/DEPLOYMENT.md` for detailed instructions.

---

## Connect ChatGPT

In ChatGPT settings, add a custom MCP server:

| Field | Value |
|-------|-------|
| **Name** | OpenReflect |
| **MCP Server URL** | `https://your-service.a.run.app/sse` |
| **Authentication** | None |

---

## Documentation

| Document | Purpose |
|----------|---------|
| `mcp-server-python/docs/DEPLOYMENT.md` | Cloud Run deployment guide |
| `agent-collab/decisions/` | Architecture decisions |
| `agent-collab/reviews/` | Code analysis and gotchas |

---

## License

This project is for experimental and learning purposes.

---

## Feature Completion Status

*Last Updated: 2025-12-21 21:36:53 UTC*

| Feature Category | Feature | Completion % | Reason for Incompleteness | Phase(s) |
|-----------------|---------|--------------|---------------------------|----------|
| **Core MCP Protocol** | JSON-RPC 2.0 Support | 95% | Missing some edge case error codes; basic protocol works | MVP, ALPHA, BETA |
| | Initialize Handshake | 100% | Fully implemented with protocol version and capabilities | MVP, ALPHA, BETA |
| | Tools Discovery (tools/list) | 100% | Complete implementation | MVP, ALPHA, BETA |
| | Tool Execution (tools/call) | 100% | Complete with proper error handling | MVP, ALPHA, BETA |
| | Prompts Discovery (prompts/list) | 100% | Complete implementation | MVP, ALPHA, BETA |
| | Prompt Retrieval (prompts/get) | 100% | Complete implementation | MVP, ALPHA, BETA |
| | SSE Transport | 90% | Basic SSE works; session management could be more robust | MVP, ALPHA, BETA |
| | Message Endpoint | 95% | Works but session_id parameter not fully utilized | MVP, ALPHA, BETA |
| **Memory Bank Tools** | initialize_memory_bank | 100% | Complete with Agent Engine creation/reuse | MVP, ALPHA, BETA |
| | generate_memories | 95% | Works but API response attribute handling is defensive (tries multiple names) | MVP, ALPHA, BETA |
| | retrieve_memories | 100% | Complete with similarity search support | MVP, ALPHA, BETA |
| | search_memories | 100% | Complete wrapper around retrieve_memories | MVP, ALPHA, BETA |
| | fetch_memory | 100% | Complete single memory retrieval | MVP, ALPHA, BETA |
| | create_memory | 100% | Complete with TTL support | MVP, ALPHA, BETA |
| | delete_memory | 100% | Complete implementation | MVP, ALPHA, BETA |
| | list_memories | 100% | Complete with pagination support | MVP, ALPHA, BETA |
| **Prompts** | memory_extraction_prompt | 100% | Complete prompt template | MVP, ALPHA, BETA |
| | memory_search_prompt | 100% | Complete prompt template | MVP, ALPHA, BETA |
| | memory_consolidation_prompt | 100% | Complete prompt template | MVP, ALPHA, BETA |
| **HTTP Server** | FastAPI Application | 100% | Complete with lifespan management | MVP, ALPHA, BETA |
| | Health Check Endpoint | 100% | Complete with readiness status | MVP, ALPHA, BETA |
| | Root Endpoint | 100% | Complete basic info endpoint | MVP, ALPHA, BETA |
| | CORS Middleware | 100% | Complete but allows all origins (needs config for production) | MVP, ALPHA, BETA |
| | Error Handling | 90% | Good coverage but some edge cases may not be caught | MVP, ALPHA, BETA |
| **Authentication** | Bearer Token Auth | 60% | Code exists but optional; not enforced by default | ALPHA, BETA |
| | Service Account Auth | 100% | Complete via GCP metadata service | MVP, ALPHA, BETA |
| | API Key Auth | 0% | Not implemented (documented as recommendation only) | BETA |
| | Cloud IAM Auth | 0% | Not implemented (documented as recommendation only) | BETA |
| **Input Validation** | Scope Validation | 100% | Complete validation for user scopes | MVP, ALPHA, BETA |
| | Conversation Validation | 100% | Complete validation for conversation format | MVP, ALPHA, BETA |
| | Memory Fact Validation | 100% | Complete with length limits | MVP, ALPHA, BETA |
| | JSON-RPC Validation | 85% | Basic validation; could validate more deeply | ALPHA, BETA |
| **Configuration** | Environment Variables | 100% | Complete config loading | MVP, ALPHA, BETA |
| | .env File Support | 100% | Complete for local development | MVP, ALPHA |
| | Config Validation | 90% | Basic validation; could be more strict | ALPHA, BETA |
| | Secret Manager Integration | 0% | Not implemented (documented as recommendation) | BETA |
| **Deployment** | Dockerfile | 100% | Complete multi-stage build | MVP, ALPHA, BETA |
| | Build Script | 100% | Complete build.sh script | MVP, ALPHA, BETA |
| | Cloud Run Template | 100% | Complete YAML template | MVP, ALPHA, BETA |
| | User Provisioning Script | 100% | Complete provision_user.py | MVP, ALPHA, BETA |
| | Golden Image Strategy | 100% | Complete deployment pattern | MVP, ALPHA, BETA |
| | Environment Variable Injection | 100% | Complete in deployment configs | MVP, ALPHA, BETA |
| **Error Handling** | Exception Catching | 90% | Good coverage; some Vertex AI errors may need specific handling | MVP, ALPHA, BETA |
| | Error Formatting | 100% | Complete MCP-compatible error responses | MVP, ALPHA, BETA |
| | Logging | 85% | Basic logging; could use structured logging | ALPHA, BETA |
| | Error Recovery | 70% | Basic recovery; no retry logic for transient failures | ALPHA, BETA |
| **Data Formatting** | Memory Formatting | 100% | Complete consistent formatting | MVP, ALPHA, BETA |
| | Conversation Event Formatting | 100% | Complete Vertex AI format conversion | MVP, ALPHA, BETA |
| | TTL Expiration Formatting | 100% | Complete ISO format conversion | MVP, ALPHA, BETA |
| | Response Formatting | 100% | Complete MCP-compatible responses | MVP, ALPHA, BETA |
| **State Management** | App State Container | 100% | Complete singleton pattern | MVP, ALPHA, BETA |
| | Initialization Tracking | 100% | Complete readiness checks | MVP, ALPHA, BETA |
| | State Reset | 100% | Complete reset functionality | MVP, ALPHA, BETA |
| **Testing** | Unit Tests | 20% | Only basic HTTP endpoint tests exist | ALPHA, BETA |
| | Integration Tests | 10% | Test script exists but not comprehensive | ALPHA, BETA |
| | End-to-End Tests | 5% | Basic examples only; no automated E2E suite | ALPHA, BETA |
| | Load Testing | 0% | Not implemented (documented examples only) | ALPHA, BETA |
| | Mock/Stub Support | 0% | No mocking framework setup | ALPHA, BETA |
| **Monitoring** | Health Check Metrics | 100% | Complete health endpoint | MVP, ALPHA, BETA |
| | Cloud Run Metrics | 100% | Automatic via Cloud Run | MVP, ALPHA, BETA |
| | Custom Metrics | 0% | Not implemented (documented as recommendation) | ALPHA, BETA |
| | Log-Based Metrics | 0% | Not implemented (documented as recommendation) | ALPHA, BETA |
| | Alert Policies | 0% | Not implemented (documented as recommendation) | ALPHA, BETA |
| | Dashboards | 0% | Not implemented (documented as recommendation) | ALPHA, BETA |
| | SLO Configuration | 0% | Not implemented (documented as recommendation) | BETA |
| **Security** | Input Sanitization | 85% | Basic validation; could add more XSS/injection protection | ALPHA, BETA |
| | Rate Limiting | 0% | Not implemented (documented as recommendation) | BETA |
| | DDoS Protection | 0% | Relies on Cloud Run defaults only | BETA |
| | Secret Management | 0% | Uses env vars; Secret Manager not integrated | BETA |
| | Audit Logging | 0% | Basic logs only; no structured audit trail | BETA |
| | VPC Connector | 0% | Not configured (documented as recommendation) | BETA |
| | Container Scanning | 0% | Not automated (documented as manual process) | ALPHA, BETA |
| | Dependency Scanning | 0% | Not automated (documented as manual process) | ALPHA, BETA |
| **Documentation** | README | 100% | Complete with architecture and quick start | MVP, ALPHA, BETA |
| | Deployment Guide | 100% | Complete DEPLOYMENT.md | MVP, ALPHA, BETA |
| | Security Guide | 100% | Complete SECURITY.md with checklist | ALPHA, BETA |
| | Monitoring Guide | 100% | Complete MONITORING.md | ALPHA, BETA |
| | Integration Testing Guide | 100% | Complete INTEGRATION_TESTING.md | ALPHA, BETA |
| | Verification Checklist | 100% | Complete VERIFICATION_CHECKLIST.md | MVP, ALPHA, BETA |
| | Code Comments | 85% | Good coverage; some complex logic could use more | MVP, ALPHA, BETA |
| | API Documentation | 80% | Tool docstrings exist; could add OpenAPI spec | ALPHA, BETA |
| **Operational** | Graceful Shutdown | 90% | Lifespan context exists; could be more robust | ALPHA, BETA |
| | Cold Start Optimization | 70% | Basic; no keepalive mechanism implemented | BETA |
| | Connection Pooling | 0% | Not implemented (Vertex AI client handles this) | BETA |
| | Retry Logic | 0% | Not implemented for transient failures | BETA |
| | Circuit Breaker | 0% | Not implemented | BETA |
| **Code Quality** | Type Hints | 90% | Good coverage; some return types could be more specific | MVP, ALPHA, BETA |
| | Code Organization | 100% | Excellent separation of concerns | MVP, ALPHA, BETA |
| | Error Messages | 85% | Generally clear; some could be more descriptive | MVP, ALPHA, BETA |
| | Dependency Management | 95% | Requirements.txt complete; minor version conflicts noted | MVP, ALPHA, BETA |

### Phase Summary

- **MVP Features**: 48 features — Core functionality required for initial release
- **ALPHA Features**: 15 features — Testing infrastructure, basic monitoring, and security hardening  
- **BETA Features**: 18 features — Production readiness, advanced security, and performance optimization

**Overall Assessment**: Core functionality is ~95% complete and ready for testing. Security, monitoring, and testing infrastructure are documented but not fully implemented, which is acceptable for a testing environment but needs attention before production.