# OpenReflect GCP Vertex MemoryCore

OpenReflect GCP Vertex MemoryCore is a prototype Model Context Protocol
server for connecting an MCP-capable client to Google Cloud Vertex AI memory
infrastructure.

The goal is simple: expose a small set of memory tools over MCP so an AI client
can initialize a memory backend, generate memories from conversation context,
retrieve relevant memories, and manage stored facts through a deployable Cloud
Run service.

## Why it exists

LLM sessions are usually stateless. Useful assistants and tools need a way to
carry durable, inspectable memory without putting every past interaction back
into the prompt. This repository explores one concrete bridge between MCP
clients and Google Cloud's managed AI platform.

The project is intentionally narrow. It is not a complete identity, consent, or
production memory governance system. It is a working integration surface for
experimentation, evaluation, and extension.

## Core idea

```text
MCP client
    |
    |  JSON-RPC over SSE / HTTP
    v
MemoryCore MCP server
    |
    |  Google Cloud client APIs
    v
Vertex AI Agent Engine / Memory Bank
```

The server presents memory operations as MCP tools:

- `initialize_memory_bank`
- `generate_memories`
- `retrieve_memories`
- `search_memories`
- `fetch_memory`
- `create_memory`
- `delete_memory`
- `list_memories`

The HTTP transport is designed for Cloud Run, with local development support
through standard Python tooling.

## Design principles

- Keep the MCP surface small and explicit.
- Prefer deployable examples over abstract diagrams.
- Keep environment-specific configuration out of the public repository.
- Make local development possible without requiring a pre-provisioned memory
  engine.
- Treat authentication, tenancy, and governance as production hardening work,
  not as assumptions hidden inside the prototype.

## Repository layout

```text
.
├── mcp-server-python/
│   ├── src/                    # MCP tools, HTTP server, config, validation
│   ├── deploy/                 # Cloud Run deployment helpers/templates
│   ├── docs/                   # Deployment, security, monitoring, testing docs
│   ├── examples/               # Local usage examples
│   ├── tests/                  # Basic HTTP/server tests
│   ├── Dockerfile
│   └── requirements.txt
├── README.md
└── .gitignore
```

## Current status

This is prototype code. The main server path supports MCP tool discovery and
tool calls, SSE/HTTP transport, local execution, container deployment, and
Cloud Run deployment templates.

Areas still expected to need hardening before production use:

- authentication and authorization policy
- tenant and user isolation
- automated end-to-end tests
- structured audit logging
- dependency and container scanning
- deployment-specific monitoring and alerting

## Quick start

```bash
cd mcp-server-python
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
export GOOGLE_CLOUD_LOCATION=us-central1

python -m uvicorn src.server_http:app --host 0.0.0.0 --port 8080
```

For Cloud Run deployment details, see
`mcp-server-python/docs/DEPLOYMENT.md`.

## Configuration

Use environment variables for deployment-specific settings:

```text
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key
AGENT_ENGINE_NAME=projects/YOUR_PROJECT_ID/locations/YOUR_LOCATION/reasoningEngines/YOUR_ENGINE_ID
```

Do not commit live credentials, private project IDs, generated service account
keys, or deployment proof logs.

## Public/private model

This public repository contains generalized prototype code, documentation,
examples, and deployment templates.

Private operational forks or downstream control-plane repositories should hold:

- real Google Cloud project IDs
- service account material
- live deployment manifests
- internal logs and proof transcripts
- environment-specific MCP client configuration

That separation keeps the public project reusable while preserving operational
privacy for real deployments.

## License

No license has been selected yet. Treat the code as source-available until a
license is added.
