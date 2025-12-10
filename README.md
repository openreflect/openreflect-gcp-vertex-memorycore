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

gcloud run deploy vertex-memory-bank-mcp \
  --image gcr.io/$PROJECT_ID/vertex-memory-bank-mcp:latest \
  --region us-central1 \
  --allow-unauthenticated
```

See `mcp-server-python/docs/DEPLOYMENT.md` for detailed instructions.

---

## Connect ChatGPT

In ChatGPT settings, add a custom MCP server:

| Field | Value |
|-------|-------|
| **Name** | Vertex Memory Bank |
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
