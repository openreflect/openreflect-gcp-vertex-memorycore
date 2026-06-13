# Provenance Model

This file describes the proposed data model for MemoryCore provenance.

## Design Intent

The provenance model should be append-friendly, inspectable, and independent of
any one MCP client. It should track memory operations without requiring every
client to expose identical identity or session metadata.

## Core Entities

### Client

Represents the tool or runtime that performed a memory operation.

Suggested fields:

```json
{
  "client_id": "client-generated-or-server-assigned-id",
  "client_name": "ChatGPT",
  "client_type": "mcp_client",
  "client_version": "optional-client-version",
  "transport": "sse|stdio|http|other"
}
```

### Conversation

Represents the interaction context that produced or consumed a memory.

Suggested fields:

```json
{
  "conversation_id": "opaque-client-or-server-id",
  "client_id": "client-generated-or-server-assigned-id",
  "user_scope": {
    "user_id": "demo_user_123"
  },
  "started_at": "RFC3339 timestamp",
  "metadata": {}
}
```

### Memory Record

Wraps the underlying Vertex AI Memory Bank memory with provenance metadata.

Suggested fields:

```json
{
  "memory_name": "vertex-memory-resource-name",
  "scope": {
    "user_id": "demo_user_123"
  },
  "fact": "Standalone memory fact",
  "created_at": "RFC3339 timestamp",
  "updated_at": "RFC3339 timestamp",
  "source": {
    "source_type": "generated|explicit|imported",
    "client_id": "client-generated-or-server-assigned-id",
    "conversation_id": "opaque-client-or-server-id",
    "operation_id": "server-operation-id"
  }
}
```

### Provenance Event

Append-only event that records what happened to a memory or memory query.

Suggested fields:

```json
{
  "event_id": "server-operation-id",
  "event_type": "memory.created",
  "occurred_at": "RFC3339 timestamp",
  "client_id": "client-generated-or-server-assigned-id",
  "conversation_id": "opaque-client-or-server-id",
  "scope": {
    "user_id": "demo_user_123"
  },
  "memory_name": "optional-vertex-memory-resource-name",
  "tool_name": "create_memory",
  "inputs_hash": "optional-redacted-input-hash",
  "result": "success|error",
  "metadata": {}
}
```

## Storage Options

Possible storage targets:

- Vertex AI Memory Bank metadata, if supported by the API surface.
- A separate structured store such as Firestore.
- A durable append-only log in Cloud Logging or BigQuery.
- A hybrid approach: memory facts in Vertex AI, provenance events in a separate
  audit store.

The preferred direction is likely hybrid. Memory Bank remains responsible for
memory retrieval, while a structured provenance store records operational
history.

## Privacy Constraint

The provenance layer should avoid storing full prompt or conversation text by
default. Store stable IDs, redacted summaries, hashes, timestamps, tool names,
and client/workflow metadata unless a deployment explicitly opts into richer
capture.

