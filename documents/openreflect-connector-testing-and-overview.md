## OpenReflect Connector — Testing & Overview

Date: 2026-01-02

### 1) Web UI testing (ChatGPT connector experience)

**How testing worked**
- The OpenReflect connector was invoked directly in ChatGPT using `@OpenReflect …` commands.
- For most actions, ChatGPT displayed a **per-tool permission prompt** (allow/deny) before the tool call executed.
- The prompt indicated that certain metadata (e.g., approximate location/device info) may be shared with the tool, depending on the action.

**Tools discovered (from the connector)**
The connector exposes these tools:
- `connect_account` (deprecated in ChatGPT; OAuth is handled at the connector level)
- `connect_with_key`
- `check_connection`
- `disconnect`
- `initialize_memory_bank`
- `generate_memories`
- `retrieve_memories`
- `search_memories`
- `fetch_memory`
- `create_memory`
- `delete_memory`
- `list_memories`

**Tool-by-tool test results (from live browser testing)**

| Tool | Status | What we observed in ChatGPT |
|---|---:|---|
| `check_connection` | ✅ Functional | Returned “OK / session active” and confirmed the connector was responsive. |
| `list_memories` | ✅ Functional | Returned count + an empty list initially (“no memories stored yet”). Required user approval. |
| `create_memory` | ✅ Functional | Created a memory successfully and returned a full memory resource ID. Required user approval. **Note:** when we tried supplying a separate `source`, it was not stored (tool accepts only the fact/TTL). |
| `retrieve_memories` | ✅ Functional | Performed similarity retrieval and returned matching memories plus similarity scores. Required user approval. |
| `fetch_memory` | ✅ Functional | Fetched a single memory by full resource name and returned the fact + metadata. Required user approval. |
| `delete_memory` | ✅ Functional | When given a non-existent ID, returned a clear `404 NOT_FOUND`, which is expected behavior for idempotent deletes. Required user approval. |
| `search_memories` | ✅ Functional | Successfully returned matching memory for query “Python” with a similarity score. Required user approval. |
| `generate_memories` | ✅ Functional (no new memory extracted in this run) | The call succeeded, but it produced “no memory content” for the supplied conversation sample (i.e., it ran but didn’t add new facts). Required user approval. |
| `connect_with_key` | ✅ Functional | Connected using a user-provided key and returned a derived `user_id`. Required user approval. |
| `disconnect` | ⚠️ Partially functional in ChatGPT | Tool invocation occurred, but the session reset was **blocked by the platform** (connector-level auth/session handling can supersede app-level session state). |
| `initialize_memory_bank` | ✅ Functional | Returned `already_initialized` and showed current configuration (safe read-only behavior when already set up). Required user approval. |
| `connect_account` | ⚠️ Deprecated (not tested) | Tool exists, but the server marks it deprecated for ChatGPT since OAuth is handled at the connector/transport level. |

### 2) Two-paragraph product description (for non-technical users)

OpenReflect is a “memory bank” connector you can attach to ChatGPT so it can **remember and retrieve information you choose across chats**—things like preferences, recurring context, or key facts you want available later. Instead of relying on ChatGPT’s built-in memory, OpenReflect stores your information in your own dedicated backend (Google Vertex AI Memory Bank), so you get a consistent, portable source of truth that can be reused over time.

Its core features are **saving, searching, and managing memories on demand**: you can create memories explicitly, list what’s stored, retrieve relevant memories via semantic search, fetch a single memory by ID, and delete items you don’t want kept. It also supports **optional automatic memory generation** from a conversation (when it detects something worth saving), plus flexible connection options—**OAuth sign-in** or a **shared key** you can reuse across different AI assistants to access the same memory store—while keeping control in your hands through per-action permission prompts.

### 3) Top 10 selling points (and market differentiation)

- **1) Persistent, cross-chat memory (continuity)**: The assistant can recall user preferences, context, and past decisions across sessions.  
  - **Differentiation**: retention duration (days vs “forever”), scope (per-user vs per-team), portability (single app vs cross-assistant), and recall quality.

- **2) User-controlled capture (opt-in memory)**: Users can explicitly “save this” and edit/delete what’s stored, reducing surprises.  
  - **Differentiation**: how explicit/transparent capture is (auto vs approve), quality of review UI, and whether the system can justify why something was stored.

- **3) Semantic recall (natural-language retrieval)**: Find relevant memories with a query like “my preferences for X,” not exact keywords.  
  - **Differentiation**: ranking quality, relevance tuning (recency/importance), explainability (“why this was retrieved”), and handling duplicates/conflicts.

- **4) Privacy, data control, and ownership**: Memories can live in a dedicated backend rather than only inside the assistant vendor.  
  - **Differentiation**: where data is stored (vendor-hosted vs customer-controlled cloud), encryption posture, data residency options, and export/delete guarantees.

- **5) Vendor/model portability (avoid lock-in)**: Same memory layer works across models and assistants.  
  - **Differentiation**: standards support (e.g., MCP-style interfaces), ease of switching clients, and identity strategy (OAuth vs shared key vs enterprise SSO).

- **6) Fine-grained permissions + safety prompts**: Each action (list/search/create/delete) can be consented to and auditable.  
  - **Differentiation**: granularity (per-tool/per-field), scope controls, audit logging depth, and “data minimization” defaults.

- **7) Memory lifecycle management (edit/forget/TTL)**: Users can prune stale info, set expiration, and prevent “creeping” profiles.  
  - **Differentiation**: TTL/retention policies, bulk operations, conflict resolution, and how quickly “forget” propagates across caches/indexes.

- **8) Better personalization without retraining**: Personalization comes from retrieved memories, not custom model training.  
  - **Differentiation**: latency and reliability of retrieval, how well it blends with conversation context, and guardrails that prevent over-personalization.

- **9) Workflow and system integration**: Memories can be created from conversations or external systems (docs, CRM, tickets).  
  - **Differentiation**: connector breadth, ingest quality (structure, dedupe), automation (rules/triggers), and how well it handles team/enterprise sources.

- **10) Enterprise readiness (governance at scale)**: Admin controls for teams, compliance posture, and operational visibility.  
  - **Differentiation**: RBAC/tenant isolation, compliance features (audit, retention policies), observability (metrics/traces), and cost controls (quotas/limits).

