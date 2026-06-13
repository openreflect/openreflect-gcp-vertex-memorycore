# Provenance Layer

This directory marks the intended provenance layer for MemoryCore.

The current server exposes Vertex AI Memory Bank through MCP tools. It can
create, generate, retrieve, search, fetch, list, and delete scoped memories.
The provenance layer described here is the next architectural layer: it records
where memory operations came from, which client or workflow used them, and how
context moved between MCP-capable clients.

This directory is intentionally separate from the root README. The public
description should remain conservative until the provenance layer is implemented
in code.

## Project Stage

The provenance layer is in an early project cycle.

This public directory records the intended architecture, vocabulary, scenarios,
and implementation boundary. Active design, prototyping, deployment wiring, and
private operational testing may continue in a private repository, private fork,
or downstream control-plane project before selected pieces are promoted back
into this public codebase.

That split is deliberate:

- public files describe the generalized architecture and reusable model;
- private work can carry environment-specific details, live deployment values,
  test traces, and operational findings;
- promoted public changes should be generalized, documented, and safe to reuse.

## Goal

MemoryCore should support shared memory across MCP-capable clients while keeping
the path of each memory inspectable.

The system should be able to answer questions such as:

- Which client created this memory?
- Which conversation or workflow produced it?
- Was the memory generated from conversation text or created explicitly?
- Which client retrieved it later?
- Did the memory participate in a handoff between clients?
- Was it updated, expired, or deleted?

## Intended Clients

Examples of MCP-capable or MCP-adjacent clients this layer should be able to
represent:

- ChatGPT
- Gemini
- Claude Desktop
- Goose
- local MCP clients
- custom agent runtimes

Client support should be represented through metadata, not hard-coded client
assumptions.

## Files

- `model.md` defines the proposed provenance entities and fields.
- `events.md` defines event types for memory creation, retrieval, update, and
  cross-client handoff.
- `scenarios.md` gives concrete cross-client continuity examples.
- `roadmap.md` lists implementation milestones.

## Implementation Boundary

Do not treat this directory as proof that provenance is already implemented.

Current implementation status:

- MCP tool transport: implemented.
- Vertex AI Memory Bank operations: implemented.
- Scope-based memory access: implemented.
- First-class provenance records: not implemented.
- Structured audit log: not implemented.
- Cross-client handoff records: not implemented.
