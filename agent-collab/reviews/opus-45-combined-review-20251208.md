# Opus-4.5 — Combined Review (2025-12-08)

## Scope
Merge critical findings from prior assessments and `opus-45-reviewer-121025-0200.md`, focusing on Cloud Run deploy readiness and ChatGPT web MCP connector functionality.

## Critical Issues (must fix)
1) Auth gating when token unset (`mcp-server-python/src/server_http.py`)
   - Current: `_authorize` 401s if `CONNECTOR_BEARER_TOKEN` is not set.
   - Impact: Dev/tests fail without token; contradicts “optional” auth; health/root intended open.
   - Fix: Allow access when token unset; enforce bearer only when set. Tests that set token must send header.

2) Env/config gating (`src/config.py`, `src/server.py`)
   - `is_valid()` requires project_id/api_key AND `AGENT_ENGINE_NAME`; missing engine → `/health` 503 and tools unusable.
   - Fix: Ensure Cloud Run sets `AGENT_ENGINE_NAME` (and project/location/token for prod). This is required for ready state.

3) Duplicate dependency spec (`requirements.txt`)
   - `google-genai` listed twice with different mins (>=1.40.0 and >=0.1.0).
   - Fix: Remove the lower/duplicate; keep `google-genai>=1.40.0`.

4) Protocol version alignment
   - Server/tests use `2024-12-01`. If ChatGPT MCP expects a different version, handshake could fail.
   - Fix: Confirm ChatGPT expectation; keep server/tests/scripts in sync.

5) Tests missing auth headers (if token enforced) (`tests/test_http_server.py`, `tests/test_local_docker.sh`)
   - If token set in CI, tests must send Authorization; if running without token, allow open mode in `_authorize`.
   - Fix: Add headers/env token to tests or rely on open mode when token unset.

## Medium / Optional
6) pyproject.toml missing HTTP deps
   - Affects `pip install .` users; add fastapi/uvicorn/httpx to dependencies if packaging this way.

## Good / Ready
7) MCP content wrapping implemented (`src/formatters.py`); SSE `/sse` and `/sse/` supported; root `/` present; tools include search/fetch helpers.
8) Cloud Run template: minScale=1, maxScale=1 (per-user), port 8080; ensure envs set. Verify registry (GCR vs AR) as needed.

## Suggested Common Fix Actions
- Auth gate: allow open when token unset; enforce bearer when set.
- Env completeness: set `GOOGLE_CLOUD_PROJECT` (or `GOOGLE_API_KEY`), `GOOGLE_CLOUD_LOCATION`, `AGENT_ENGINE_NAME`, `CONNECTOR_BEARER_TOKEN` (prod).
- Dependencies: remove duplicate `google-genai` entry.
- Protocol: confirm version with ChatGPT MCP; sync server + tests/scripts.
- Tests: if token enforced, add Authorization headers; else rely on open mode in dev.
