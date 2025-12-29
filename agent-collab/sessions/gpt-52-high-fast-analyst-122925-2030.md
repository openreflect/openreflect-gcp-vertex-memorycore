# GPT-52-high-fast — OAuth + Hashed Identity Scope vs Multi-User / Multi-Session MCP (Session 122925-2030)

## Session Summary

This session answers the question:

> Theoretically, if OAuth were introduced and the (OAuth) user ID were hashed and used as the Memory Bank `scope`, and the MCP server became multi-user / multi-session, would that resolve the majority of issues discussed in this thread?

**Conclusion**: OAuth + hashed identity **solves the identity / authorization dimension** (multi-user correctness) *if* scope is derived server-side and access is enforced. It does **not** automatically solve the **global singleton / session isolation** issues in the current implementation unless you also refactor state handling (or constrain the system to a single shared engine + immutable global client).

---

## What “issues in this session” actually were

There are two separable problem classes:

### A) Multi-user identity & authorization problems

- **Who is the user?** (stable identity across ChatGPT / Claude / Gemini)
- **Can user A read/write user B’s memories?**
- **Can clients spoof another user by sending a different `scope`?**
- **Can clients access global/unscoped operations (e.g., list everything)?**

OAuth + derived identity addresses this class well.

### B) Multi-session state isolation problems (current root cause)

- The codebase stores **mutable global state** (`app.client`, `app.agent_engine`, config) and all tools read from it.
- Multiple concurrent sessions can overwrite each other’s global engine/client, causing cross-session interference even within the same “user”.

OAuth does not automatically fix this; it only gives you a reliable user identity you *can* use while redesigning session state.

---

## What OAuth + hashed identity (“user_id”) would do

Your `AUTH_DESIGN.md` already outlines the intended approach:

- On successful OAuth, extract a stable subject identifier (`sub`) and derive:
  - `user_id = "usr_" + hash(sub + secret)[:16]`
- Bind the derived `user_id` to the MCP `session_id`
- Ensure all memory operations use a server-derived scope:
  - `scope = {"user_id": user_id}`

### Why hashing the OAuth subject is good

- `sub` is stable and non-PII-ish, but still an external identifier.
- Hashing/HMAC gives you:
  - deterministic mapping (same user always maps to same internal user_id)
  - reduced accidental PII exposure in logs/URLs/tool payloads
  - easier “account linking” later (multiple auth methods can map to same user_id)

**Important detail**: For security hygiene, use an HMAC (e.g., HMAC-SHA256) rather than concatenating strings into a raw hash. The document’s “hash(sub + secret)” is directionally right but HMAC is the standard.

---

## What this would resolve (majority of multi-user problems)

If implemented as “server-derived scope + enforced access”, it resolves:

### 1) Client spoofing of `scope`

Today, tools accept `scope: Dict[str, str]` from the client (e.g., `{"user_id": "alice123"}`), which means a malicious client could supply another user’s scope.

With OAuth:
- Server binds session → user_id
- Tools ignore client-supplied scope and use server-derived scope

Result: clients cannot impersonate other users by sending an arbitrary `scope`.

### 2) Cross-user memory leakage for scoped APIs

Vertex Memory Bank APIs that are scoped (generate/retrieve/create with `scope=...`) will correctly isolate users *as long as the scope is enforced server-side*.

### 3) Usable multi-client identity

OAuth `sub` is stable across sessions; the derived `user_id` gives you a consistent internal identity that can work across ChatGPT, Claude Desktop, Gemini, etc.

---

## What it would NOT resolve (the session isolation / global singleton issues)

Even with perfect identity, the current codebase has architectural properties that still break multi-session correctness:

### 1) Global mutable `app.client` and `app.agent_engine`

The tools mutate global state at runtime:

- a new call to `initialize_memory_bank(...)` replaces `app.client` and `app.agent_engine`
- all other tools read `app.agent_engine.api_resource.name` globally

If you run multi-user or multi-session traffic in a single process, one session can clobber another session’s engine/client selection regardless of the user_id.

OAuth does not change that.

### 2) “Multi-user service” implies concurrency; concurrency makes global state bugs worse

The moment you move from “single tenant service per user” to “one shared service for many users”, you:
- increase concurrent session count
- increase frequency of initialization/tool calls
- increase likelihood of cross-session overwrites

So OAuth can actually make the system *feel* “more correct” while leaving a latent concurrency bug that manifests under load.

---

## The key architecture fork: shared engine vs per-user/per-session engines

Whether OAuth+scope fixes “most issues” depends heavily on how you treat the Agent Engine / client configuration.

### Option A (Recommended for first multi-user cut): Single shared Agent Engine + immutable global client

**Model**
- The server boots with one configured engine (`AGENT_ENGINE_NAME`) and one client (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`)
- All users share that engine
- All memory operations are scoped by server-derived `{"user_id": ...}`

**Why this resolves *most* practical issues**
- No one is calling “initialize a new engine” per session; global state is stable.
- Cross-session “engine overwrite” stops happening because there is only one engine.
- OAuth+scope gives you user separation inside the engine.

**Still required**
- Remove/disable “engine selection” and “engine creation” from normal user tools
- Enforce authorization for any unscoped operations (see below)

### Option B: Per-user engine (engine per user, shared service)

**Model**
- user_id determines which engine to use
- engine name is stored in a DB keyed by user_id (or created on first auth)

**Implications**
- OAuth is necessary (you need stable user_id) but still not sufficient:
  - you must implement per-user engine resolution, caching, and access control
  - you must remove global overwrites or fully isolate state per request/session

### Option C: Per-session engine (engine per session)

**Model**
- every new session initializes a new engine

**Implications**
- expensive, slower, and still requires strict per-session state isolation
- rarely worth it unless you’re doing very short-lived, ephemeral sandboxes

---

## Multi-session correctness requires a session-state design (OAuth is not enough)

To truly be “multi-user, multi-session” in one service process, you need:

### 1) Session → identity binding

- `session_id` must map to `user_id` (from OAuth) for the lifetime of the session
- tools must derive `scope` from this mapping

This is what `AUTH_DESIGN.md` describes (session store).

### 2) Session → execution context binding (if anything varies by session)

If anything varies per session (engine_name, project_id/location, client object):
- that data must be stored per session and looked up per tool call
- you must stop relying on global `app.*` for the dynamic parts

### 3) Distributed reality (Cloud Run scaling) must be considered

If you allow Cloud Run to scale to multiple instances:
- an in-memory session store is per-instance
- `/message?session_id=...` might land on a different instance than the one holding the SSE connection/session mapping

So either:
- keep max instances = 1 (simple but not scalable), or
- use an external shared store (Redis/Firestore/etc) for session routing/state, or
- design a stateless mechanism (e.g., signed token carrying user_id) plus a way to route responses to the correct SSE stream (harder).

OAuth does not solve this; it just supplies identity.

---

## Critical security note: “scope solves privacy” is only true if you remove unscoped tools

Even with OAuth-derived scope, a multi-user server can still leak data if you expose tools that operate on “all memories” or on arbitrary memory resource names.

Examples of risky surfaces in a shared engine model:

- `list_memories`: typically lists across the engine, not “for this scope”
- `fetch_memory(memory_name=...)`: if the caller can guess/obtain a name, they can fetch other users’ memory records
- `delete_memory(memory_name=...)`: same risk

Therefore, OAuth+scope resolves the multi-user issue only if:
- unscoped listing/fetch/delete are removed or restricted to admin
- memory_name-based access is protected (ownership check) or not exposed

---

## Practical answer to the original question (explicit)

### If you introduce OAuth + hashed user_id and ALSO enforce scope server-side:

- ✅ You solve the “multi-user identity correctness” part (who is the user, can they spoof scope, can they access other users’ scoped memories)

### But the majority of issues discussed in this session were about global mutable state and per-session isolation:

- ❌ OAuth alone does not fix global `app.client` / `app.agent_engine` overwrites
- ❌ OAuth alone does not fix session routing/state for SSE + `/message` in a scaled environment

### You can make it “resolve most issues” by combining OAuth with one of these constraints:

1) **Shared engine, immutable global client, no per-session initialization** (fastest path)
2) **Full per-session/per-user state isolation** (more work but scalable and correct)

---

## Recommended next step (design decision to make before coding)

Pick one target operating model for the next milestone:

### “Multi-user MVP”

- Shared engine
- OAuth identity → derived user_id
- Scope is server-derived; remove client-provided scope
- Remove/restrict unscoped tools (list/fetch/delete by arbitrary name)
- Max instances can remain low (even 1) until session routing is solved

### “Multi-user + scalable multi-session”

- Everything in “Multi-user MVP”, plus:
- session store that works across instances (or sticky routing guarantee)
- no global mutable engine/client state that varies across sessions
- explicit per-user/per-session context resolution for every tool call

---

## References (where this ties into the repo)

- `mcp-server-python/docs/AUTH_DESIGN.md`: defines OAuth identity and hashed user_id derivation, and binding session_id → user_id.
- `mcp-server-python/src/tools.py` + `mcp-server-python/src/app_state.py`: current global singleton mutation pattern that must be constrained or refactored for true multi-session correctness.
- `mcp-server-python/src/server_http.py`: SSE session handling and `/message` routing are where session identity/context must be threaded through tool calls for multi-session support.

