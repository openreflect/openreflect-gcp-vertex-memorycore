# Provenance Roadmap

This roadmap lists implementation steps for turning the provenance design into
code.

## Development Model

The provenance layer is early-cycle work. Some implementation experiments may
be developed privately first, especially where they involve live deployments,
real client behavior, operational traces, or environment-specific integration
details.

Public promotion criteria:

- the concept is generalized beyond one deployment;
- private identifiers, logs, and credentials have been removed;
- behavior is documented with public-safe examples;
- tests or verification notes exist for the promoted behavior;
- the root README remains accurate about what is actually implemented.

## Phase 1: Request Context Capture

- Add optional request metadata fields to MCP tool arguments:
  - `client_name`
  - `client_id`
  - `conversation_id`
  - `workflow_id`
- Preserve backward compatibility when metadata is absent.
- Add helper functions for normalizing client metadata.

## Phase 2: Operation IDs

- Generate a server-side `operation_id` for every tool call.
- Include `operation_id` in tool responses.
- Log operation IDs with sanitized structured fields.

## Phase 3: Provenance Event Sink

- Define a `ProvenanceRecorder` interface.
- Implement a no-op recorder for local development.
- Implement a structured recorder target, likely Firestore, Cloud Logging, or
  BigQuery.
- Ensure recorder failures do not break memory operations unless configured as
  strict.

## Phase 4: Memory Wrapper Metadata

- Where possible, attach source metadata to created/generated memories.
- If the Vertex AI Memory Bank API does not support arbitrary metadata, store
  the mapping in the separate provenance event sink.

## Phase 5: Handoff Semantics

- Add optional handoff fields:
  - `handoff_id`
  - `from_client`
  - `to_client`
  - `handoff_reason`
- Record `handoff.started` and `handoff.completed` events.
- Expose a helper tool for finding handoff-related memories.

## Phase 6: Policy and Redaction

- Add configurable redaction for queries and facts.
- Add per-deployment controls for whether to store:
  - raw query text
  - hashed query text
  - memory names only
  - summarized source snippets
- Document defaults clearly.

## Phase 7: Tests

- Unit test event creation and redaction.
- Integration test tool calls with a no-op recorder.
- Integration test structured recorder behavior with a local emulator or
  mockable backend.
- Add regression tests for clients that omit metadata.
