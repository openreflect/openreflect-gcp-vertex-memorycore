# Cross-Client Scenarios

These scenarios describe the continuity behavior MemoryCore should support once
the provenance layer is implemented.

## Scenario 1: Research to Implementation

1. A user starts source-grounded research in ChatGPT.
2. ChatGPT calls `generate_memories` for durable findings.
3. MemoryCore records `memory.generated` with ChatGPT as the source client.
4. The user opens Claude Desktop for implementation planning.
5. Claude Desktop calls `search_memories` for the same user scope.
6. MemoryCore records `memory.searched` and links the retrieval to the prior
   ChatGPT-generated memories.

Outcome: the implementation client can pick up the research context without
requiring copied transcript blocks.

## Scenario 2: Gemini Research to Goose Local Work

1. Gemini performs research or analysis.
2. The relevant observations are stored as scoped memories.
3. Goose runs locally against the same MemoryCore endpoint.
4. Goose retrieves the stored observations during a local coding workflow.

Outcome: cloud-side analysis can become local development context while the
memory records preserve where the observations came from.

## Scenario 3: Explicit User Preference Shared Across Clients

1. A user tells one client a stable preference.
2. That client calls `create_memory`.
3. Another client retrieves memories for the same scope later.
4. The second client can adapt behavior based on the explicit preference.

Outcome: preferences do not need to be re-entered in every client.

## Scenario 4: Auditable Deletion

1. A user asks a client to forget a fact.
2. The client calls `delete_memory`.
3. MemoryCore deletes the memory from Vertex AI Memory Bank.
4. The provenance layer records a sanitized `memory.deleted` event.

Outcome: the deletion is operationally inspectable without retaining the
deleted fact in plain text.

## Scenario 5: Multi-Agent Workflow

1. A planning agent creates memories describing decisions and constraints.
2. A coding agent retrieves those memories before editing code.
3. A review agent searches for relevant decisions before reviewing changes.
4. The provenance log records each client or agent interaction with the memory
   layer.

Outcome: multiple tools share continuity through explicit records rather than
implicit prompt inheritance.

