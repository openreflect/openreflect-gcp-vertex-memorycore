# Provenance Events

This file defines proposed event types for MemoryCore provenance.

## Event Naming

Use simple dotted event names:

```text
memory.created
memory.generated
memory.retrieved
memory.searched
memory.fetched
memory.deleted
memory.expired
handoff.started
handoff.completed
client.connected
client.disconnected
```

## Memory Events

### `memory.generated`

Recorded when `generate_memories` extracts memories from conversation events.

Useful fields:

- client
- conversation
- scope
- source event count
- generated memory names
- operation result

### `memory.created`

Recorded when `create_memory` stores an explicit fact.

Useful fields:

- client
- conversation, if available
- scope
- memory name
- TTL, if provided
- operation result

### `memory.retrieved`

Recorded when `retrieve_memories` returns all memories for a scope.

Useful fields:

- client
- conversation, if available
- scope
- returned memory names
- count
- operation result

### `memory.searched`

Recorded when a query-based memory search runs.

Useful fields:

- client
- conversation, if available
- scope
- query hash or redacted query
- top_k
- returned memory names
- operation result

### `memory.deleted`

Recorded when `delete_memory` removes a memory.

Useful fields:

- client
- scope, if resolvable
- memory name
- operation result

## Handoff Events

### `handoff.started`

Recorded when one client creates or retrieves context intended for another
client or workflow.

Example:

```json
{
  "event_type": "handoff.started",
  "from_client": "ChatGPT",
  "to_client": "Claude Desktop",
  "scope": {
    "user_id": "demo_user_123"
  },
  "memory_names": [
    "projects/.../memories/..."
  ]
}
```

### `handoff.completed`

Recorded when another client retrieves and uses memory associated with a prior
handoff.

This event should make cross-client continuity visible without requiring raw
conversation transcripts to be copied between clients.

## Error Events

Every tool event should be recordable with `result: "error"` and a sanitized
error code or message category.

Do not write secrets, bearer tokens, service account details, or full private
conversation text into provenance events by default.

