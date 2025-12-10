OpenReflect Implementation Plan (ChatGPT web MCP) — 2025-12-08

Assumptions
- Target client: ChatGPT web MCP using SSE `/sse` and JSON-RPC POST `/message` (not Cursor).
- Project defaults: `directed-asset-479716-f6`, region `us-central1` (override if needed).
- Auth: require `CONNECTOR_BEARER_TOKEN` in production (Authorization: Bearer ...).
- Config validity: must have (`GOOGLE_CLOUD_PROJECT` or `GOOGLE_API_KEY`) AND `AGENT_ENGINE_NAME`; otherwise server stays uninitialized.
- Artifacts already exist: `mcp-server-python/Dockerfile`, `deploy/build.sh`, `deploy/cloud-run-template.yaml`, `src/server_http.py` (HTTP/SSE), `examples/user_client_config.json`. The old `.cursor` plan was removed; do not recreate those files.

Steps (concise, numbered)
1) Verify config/env: Ensure Cloud Run envs include `GOOGLE_CLOUD_PROJECT` (or `GOOGLE_API_KEY`), `GOOGLE_CLOUD_LOCATION`, `AGENT_ENGINE_NAME`, `CONNECTOR_BEARER_TOKEN`; confirm service account has `roles/aiplatform.user` and `roles/run.invoker` (or equivalent).
2) Build & push image: From `mcp-server-python/`, run `./deploy/build.sh` (adjust PROJECT_ID/registry if needed); ensure `gcloud auth configure-docker` for the chosen registry.
3) Deploy to Cloud Run: Apply `deploy/cloud-run-template.yaml` with substitutions (SERVICE_NAME, REGION, IMAGE_URL, AGENT_ENGINE_NAME, CONNECTOR_BEARER_TOKEN, SERVICE_ACCOUNT_EMAIL); or use `gcloud run deploy` with equivalent flags. Keep port 8080.
4) Enforce auth stance: In Cloud Run, require bearer token (or IAM) for `/sse` and `/message`; set `CONNECTOR_BEARER_TOKEN` and document expected header.
5) Validate health: `curl -i https://SERVICE_URL/health` (200 when ready; 503 if initializing/not_configured).
6) Validate SSE handshake: `curl -N -H "Authorization: Bearer $TOKEN" https://SERVICE_URL/sse` and confirm first event is `event: endpoint` with data pointing to `/message?session_id=...`.
7) Validate JSON-RPC /message:
   - initialize: `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}`
   - tools/list: `{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}`
   - prompts/list: `{"jsonrpc":"2.0","id":3,"method":"prompts/list","params":{}}`
   - tools/call sample: fill `name` and `arguments` from tools/list response.
   POST with `Content-Type: application/json` and bearer header if required.
8) Address test gap: Either add a root `/` route returning 200 JSON or adjust `tests/test_http_server.py` to remove `/` expectation.
9) Update docs for ChatGPT web MCP: In `docs/DEPLOYMENT.md` (and related), replace Cursor references with ChatGPT web MCP instructions, include the above curls/JSON samples, and state env requirements (project/api_key + AGENT_ENGINE_NAME).
10) Security/perf checks: Confirm `CONNECTOR_BEARER_TOKEN` required in prod; consider Cloud Run min instances if cold-start latency is an issue; validate SSE keepalive (15s) acceptable for client.

Validation checklist (copy/paste)
- Health: `curl -i https://SERVICE_URL/health`
- SSE: `curl -N -H "Authorization: Bearer $TOKEN" https://SERVICE_URL/sse`
- JSON-RPC initialize: `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}`
- JSON-RPC tools/list: `{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}`
- JSON-RPC prompts/list: `{"jsonrpc":"2.0","id":3,"method":"prompts/list","params":{}}`
- JSON-RPC tools/call: use tool name/args from tools/list output.

Performance & security notes (brief)
- Cold starts likely (minScale=0); set min instances if latency-sensitive.
- Enforce bearer or IAM to avoid open endpoints; ensure logs don’t leak tokens.
- Image already slim; further size reduction optional. Keep SSE keepalive unless client requires different cadence.

Definition of done
- Cloud Run service deployed and reachable; `/health` 200 when configured.
- SSE handshake returns endpoint event; `/message` handles initialize/tools/prompts/tools.call with correct JSON-RPC IDs.
- Auth required and documented; envs set for config validity; service account has needed roles.
- Docs updated for ChatGPT web MCP (no Cursor references); tests adjusted or root route added; validation checklist passes.
