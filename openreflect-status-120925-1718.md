OpenReflect Status — 2025-12-08

Scope: mcp-server-python (exclude node_modules/.git/generated). Target client: ChatGPT web MCP (SSE `/sse`, JSON-RPC `/message`), not Cursor. Plan file `.cursor/plans/phase_0_memory_bank_implementation_checklist_9ae58932.plan.md` is stale and conflicts with current state.

Per-file findings (only nontrivial)
- `.cursor/plans/phase_0_memory_bank_implementation_checklist_9ae58932.plan.md`: Stale; asks to create HTTP/Docker/Cloud Run files already present; targets Cursor; file names differ (build-and-deploy.sh vs deploy/build.sh, cloud-run.yaml vs deploy/cloud-run-template.yaml).
- `mcp-server-python/Dockerfile`: Runs `uvicorn src.server_http:app` on 8080; slim base with build-essential; OK. Consider removing build-essential post-install to reduce image size (already rm lists). Auth/env not enforced here.
- `mcp-server-python/deploy/build.sh`: Builds/pushes gcr.io/${PROJECT_ID}/vertex-memory-bank-mcp:latest; assumes GCR and PROJECT_ID default; no Artifact Registry option; gcloud auth configure-docker commented.
- `mcp-server-python/deploy/cloud-run-template.yaml`: Env vars for project/location/AGENT_ENGINE_NAME/CONNECTOR_BEARER_TOKEN; minScale 0/maxScale 1; no concurrency setting; assumes bearer token provided; serviceAccount required.
- `mcp-server-python/src/config.py`: `is_valid()` requires (GOOGLE_CLOUD_PROJECT or GOOGLE_API_KEY) AND AGENT_ENGINE_NAME—plan/docs do not emphasize; if missing, server starts but remains uninitialized.
- `mcp-server-python/src/app_state.py`: `is_ready()` requires initialized and agent_engine; reset helper; OK.
- `mcp-server-python/src/server.py`: FastMCP server; `run_http()` delegates to `server_http`; relies on env for config; no direct auth handling; OK.
- `mcp-server-python/src/server_http.py`: FastAPI SSE/JSON-RPC endpoints `/sse` and `/message`, health at `/health`. Auth optional via `CONNECTOR_BEARER_TOKEN`; open if unset—security risk for prod. SSE first event sends endpoint URL with session_id. JSON-RPC handles initialize/tools/prompts/ping; returns dict (FastAPI 200). No root `/` route (tests expect `/`).
- `mcp-server-python/src/tools.py`: Implements initialize_memory_bank, generate_memories, get_memories, upsert_memory, forget_memory, etc., using Vertex AI client/agent_engine in app_state. Errors if not initialized. No retries/backoff; relies on vertexai client.
- `mcp-server-python/src/prompts.py`: Registers prompt utilities; straightforward; no issues.
- `mcp-server-python/examples/user_client_config.json`: SSE URL + bearer header; aligned with `/sse`; still generic; good sample for ChatGPT MCP clients.
- `mcp-server-python/docs/DEPLOYMENT.md`: Describes per-user Cloud Run and requires CONNECTOR_BEARER_TOKEN; references Cursor client config—needs adjustment to “ChatGPT web MCP” target.
- `mcp-server-python/tests/test_http_server.py`: Exercises /health, /, /message initialize, /sse; root `/` not implemented, so test would fail; JSON-RPC bodies slightly differ from server expectations (server ignores params but expects jsonrpc 2.0).

State of completion (overall)
- Core HTTP/SSE MCP server, Dockerfile, Cloud Run template, build script, and docs exist. Plan checklist is largely already done but mislabeled. Gaps: enforce auth for prod, add root `/` or fix tests, document config validity (project/api_key + AGENT_ENGINE_NAME), and update docs from Cursor to ChatGPT web MCP. Validation commands/curls not consolidated in docs.

Optimization notes (latency/memory)
- Python 3.11 slim with uvicorn/FastAPI; reasonable. Cold starts on Cloud Run (minScale=0); consider min instances if latency-sensitive. SSE keepalive every 15s; likely fine. No obvious caching/memory pressure; watch Vertex AI client usage. Build-essential installed then removed; image could possibly drop build-essential if wheels prebuilt.
