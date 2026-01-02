# Memory Authority and Epistemology in OpenReflect

**Version**: 1.0  
**Date**: January 2, 2026  
**Authors**: Claude Opus 4.5 (AI Architect) in collaboration with OpenReflect Team  
**Status**: Architecture Design Document  
**Related**: [ARCHITECTURE_STRATEGY.md](./ARCHITECTURE_STRATEGY.md), [AUTH_DESIGN.md](./AUTH_DESIGN.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Problem: Epistemological Confusion in LLM Memory](#the-problem-epistemological-confusion-in-llm-memory)
3. [Core Principle: Source of Truth](#core-principle-source-of-truth)
4. [Memory Plane 1: Authoritative Memory](#memory-plane-1-authoritative-memory)
5. [Memory Plane 2: Experiential Memory](#memory-plane-2-experiential-memory)
6. [Why Both Are Required](#why-both-are-required)
7. [Current OpenReflect Implementation Analysis](#current-openreflect-implementation-analysis)
8. [The Critical Gap: No Authority Metadata](#the-critical-gap-no-authority-metadata)
9. [Design Rule: No Silent Overwrites](#design-rule-no-silent-overwrites)
10. [Implementation Strategy](#implementation-strategy)
11. [Vertex AI Memory Bank Integration](#vertex-ai-memory-bank-integration)
12. [Failure Modes If Ignored](#failure-modes-if-ignored)
13. [Recommended Implementation Roadmap](#recommended-implementation-roadmap)
14. [Appendix: Tool-to-Memory-Plane Mapping](#appendix-tool-to-memory-plane-mapping)

---

## Executive Summary

This document establishes the architectural foundation for **Memory Authority and Epistemology** in OpenReflect—a critical distinction between two fundamentally different types of memory that LLM systems must handle:

| Memory Type | Source | Characteristics | Example |
|-------------|--------|-----------------|---------|
| **Authoritative** | Human-authored | Deterministic, immutable, ground truth | "Remember my billing address is 123 Main St" |
| **Experiential** | Model-inferred | Probabilistic, revisable, beliefs | Model infers "User prefers dark mode" from conversation patterns |

**The Core Invariant:**

> Model-generated memory may **never** overwrite or delete authoritative memory without an explicit human instruction.

This separation is not an implementation detail—it is an **epistemological constraint** that determines system trustworthiness, auditability, and enterprise readiness.

---

## The Problem: Epistemological Confusion in LLM Memory

### What Happens Without Memory Authority Separation

Without explicit separation between authoritative and experiential memory, LLM systems suffer from:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EPISTEMOLOGICAL CONFUSION                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User: "Remember my name is Alice"                                      │
│        ↓                                                                │
│  System stores: {"fact": "User's name is Alice"}                        │
│                                                                         │
│  [Later in conversation]                                                │
│                                                                         │
│  User: "I was helping my friend Bob set up his account"                 │
│        ↓                                                                │
│  Model infers: {"fact": "User's name might be Bob"}  ← CONFLICT!        │
│                                                                         │
│  WITHOUT AUTHORITY SEPARATION:                                          │
│  - Which fact is "true"?                                                │
│  - Can the system trust its own state?                                  │
│  - How do we audit what happened?                                       │
│  - What does the user expect?                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Trust Degradation Spiral

1. **State Drift**: Model-inferred "facts" accumulate and contradict explicit user statements
2. **Loss of Auditability**: No way to trace which memories came from which source
3. **Non-Reproducible Behavior**: Same user, different sessions, different "truths"
4. **User Confusion**: "Why does the AI think I live in New York when I told it San Francisco?"
5. **Enterprise Rejection**: Compliance and governance requirements cannot be met

---

## Core Principle: Source of Truth

Every memory in the system must have a **clear authority**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MEMORY AUTHORITY MODEL                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  AUTHORITATIVE MEMORY (Ground Truth)                                    │
│  ════════════════════════════════════                                   │
│  • Created by: Human (explicit action)                                  │
│  • Modified by: Human only (explicit action)                            │
│  • Deleted by: Human only (explicit action)                             │
│  • Treated as: Fact (not subject to reinterpretation)                   │
│  • Audit trail: Complete                                                │
│                                                                         │
│  EXPERIENTIAL MEMORY (Beliefs)                                          │
│  ════════════════════════════════                                       │
│  • Created by: Model (inference from interactions)                      │
│  • Modified by: Model (can revise, merge, expand)                       │
│  • Deleted by: Model or Human                                           │
│  • Treated as: Belief (subject to revision)                             │
│  • Audit trail: Best-effort                                             │
│                                                                         │
│  INVARIANT: Experiential memory NEVER overwrites Authoritative memory   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Memory Plane 1: Authoritative Memory

### Definition

Authoritative memory consists of **explicit facts provided by a trusted external agent** (user, administrator, or policy engine).

### Characteristics

| Property | Description |
|----------|-------------|
| **Creation** | Explicit action (`create_memory` tool) |
| **Mutability** | Immutable unless explicitly deleted/updated by authorized actor |
| **Status** | Ground truth—not subject to model reinterpretation |
| **Persistence** | Permanent until explicit deletion |
| **Auditability** | Full audit trail required |

### Examples in OpenReflect Context

- User preferences: "Mitchell likes TypeScript"
- Security constraints: "Never share code outside the organization"
- Personal information: "My email is alice@example.com"
- Explicit instructions: "Always use dark mode in code examples"
- Configuration state: "Project uses Python 3.11"

### Guarantees

- ✅ **Deterministic**: Same input → same stored output
- ✅ **Auditable**: Who created, when, what
- ✅ **Reproducible**: Query returns consistent results
- ✅ **Compliant**: Safe for governance and compliance

### Mental Model

> A database record with human accountability.

---

## Memory Plane 2: Experiential Memory

### Definition

Experiential memory is **derived from model analysis of interactions over time**. It represents **beliefs, not facts**.

### Characteristics

| Property | Description |
|----------|-------------|
| **Creation** | Semantic summarization (`generate_memories` tool) |
| **Mutability** | Can be revised, merged, or expanded by model |
| **Status** | Belief—subject to revision based on new evidence |
| **Persistence** | May be consolidated, deduplicated, or pruned |
| **Auditability** | Best-effort (source conversation may be referenced) |

### Examples in OpenReflect Context

- Communication style: "User prefers concise responses"
- Inferred habits: "User typically works on backend tasks in the morning"
- Pattern recognition: "User often asks about TypeScript generics"
- Implicit preferences: "User seems to prefer functional programming style"
- Contextual beliefs: "User is working on a large refactoring project"

### Guarantees

- ✅ **Adaptive**: Evolves with interaction
- ✅ **Scalable**: Grows with conversation volume
- ✅ **Human-like recall**: Mimics natural memory formation
- ⚠️ **No uniqueness guarantee**: May have semantic duplicates
- ⚠️ **No permanence guarantee**: May be revised or merged

### Mental Model

> A cognitive belief graph, not a ledger.

---

## Why Both Are Required

Neither memory plane alone is sufficient for a production-grade LLM memory system:

### Comparison Matrix

| Requirement | Authoritative Only | Experiential Only | Both (Required) |
|-------------|-------------------|-------------------|-----------------|
| **Auditability** | ✅ Complete | ❌ Impossible | ✅ Where needed |
| **Adaptability** | ❌ Static | ✅ Dynamic | ✅ Balanced |
| **Safety** | ✅ Predictable | ❌ Unpredictable | ✅ Controlled |
| **Human-like UX** | ❌ Robotic | ✅ Natural | ✅ Best of both |
| **Enterprise Ready** | ✅ Compliant | ❌ Risky | ✅ Appropriate |
| **Scalability** | ⚠️ Manual entry | ✅ Automatic | ✅ Hybrid |

### The Synthesis

A robust LLM memory system must:

1. **Support both planes** with clear separation
2. **Never conflate them** in storage or retrieval
3. **Enforce authority hierarchy** (authoritative > experiential)
4. **Provide visibility** into which plane each memory belongs to

---

## Current OpenReflect Implementation Analysis

### Existing Tool Alignment

The current OpenReflect codebase has the **functional separation** but lacks **metadata enforcement**:

| Tool | Intended Memory Plane | Current Implementation |
|------|----------------------|------------------------|
| `create_memory` | **Authoritative** ✅ | Creates memory from explicit user input |
| `delete_memory` | **Authoritative** ✅ | Deletes specific memory by name |
| `generate_memories` | **Experiential** ⚠️ | Generates memories from conversation—no authority tagging |
| `retrieve_memories` | Both | Returns all memories without authority distinction |
| `search_memories` | Both | Searches all memories without authority distinction |
| `list_memories` | Both | Lists all memories without authority distinction |

### Code Analysis: `create_memory` (Authoritative Path)

```python
# From tools.py - This IS authoritative memory creation
@mcp.tool()
async def create_memory(
    fact: str, key: Optional[str] = None, ttl_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a memory directly.
    
    Args:
        fact: The information to remember  ← Human-provided, explicit
        ...
    """
    # Build memory data
    memory_data = {"fact": fact.strip(), "scope": scope}
    # ⚠️ NO AUTHORITY METADATA ATTACHED
```

### Code Analysis: `generate_memories` (Experiential Path)

```python
# From tools.py - This IS experiential memory generation
@mcp.tool()
async def generate_memories(
    conversation: List[Dict[str, str]],
    ...
) -> Dict[str, Any]:
    """
    Generate memories from a conversation.
    
    Analyzes conversation and extracts relevant information to remember.
    ← Model-inferred, probabilistic
    """
    # Generate memories via Vertex AI
    operation = app.client.agent_engines.generate_memories(...)
    # ⚠️ NO AUTHORITY METADATA ATTACHED
    # ⚠️ NO PROTECTION AGAINST OVERWRITING AUTHORITATIVE MEMORIES
```

### Existing Prompts Show Awareness

The `memory_consolidation_prompt` in `prompts.py` demonstrates awareness of memory conflicts:

```python
"""Review these existing memories and determine how to handle a new fact:

Existing memories:
{existing_memories}

New fact to consider:
{new_fact}

Determine if the new fact:
1. Is completely new and should be added as a separate memory
2. Updates or enhances an existing memory (specify which one and how to merge)
3. Contradicts an existing memory (specify which one should be kept)
4. Is redundant and should not be stored
"""
```

**However**, this prompt cannot enforce the authority constraint without the metadata layer.

---

## The Critical Gap: No Authority Metadata

### Current State

Memories are stored with minimal metadata:

```python
# Current memory structure (implicit)
{
    "fact": "User prefers dark mode",
    "scope": {"user_id": "usr_abc123"},
    # ❌ No authority indicator
    # ❌ No source tracking
    # ❌ No creation method
}
```

### Required State

Memories should include authority metadata:

```python
# Required memory structure
{
    "fact": "User prefers dark mode",
    "scope": {"user_id": "usr_abc123"},
    "metadata": {
        "authoritative": True,           # or False for experiential
        "source": "user_explicit",        # or "model_inferred"
        "created_by": "human",            # or "model"
        "created_at": "2026-01-02T...",
        "tool_used": "create_memory",     # or "generate_memories"
        "conversation_ref": null          # or reference for experiential
    }
}
```

### What the Gap Prevents

Without authority metadata, the system cannot:

| Capability | Status | Impact |
|------------|--------|--------|
| Prevent `generate_memories` from overwriting user facts | ❌ Impossible | Trust degradation |
| Distinguish "ground truth" from "belief" in retrieval | ❌ Impossible | Confusion |
| Audit which memories came from which source | ❌ Impossible | Compliance failure |
| Implement "no silent overwrites" invariant | ❌ Impossible | State drift |
| Allow users to manage only their explicit memories | ❌ Impossible | Poor UX |

---

## Design Rule: No Silent Overwrites

### The Invariant

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CRITICAL INVARIANT                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Model-generated memory may NOT overwrite or delete authoritative       │
│  memory without an EXPLICIT human instruction.                          │
│                                                                         │
│  This means:                                                            │
│  • generate_memories MAY update experiential beliefs                    │
│  • generate_memories MAY NOT remove or modify authoritative facts       │
│  • Even if duplicates appear semantically equivalent                    │
│                                                                         │
│  DUPLICATE FACTS ARE SAFER THAN SILENT LOSS OF AUTHORITY.              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Expected Behavior

When both memory mechanisms are used:

1. A fact is explicitly stored via `create_memory` (authoritative)
2. The model later infers the same fact via `generate_memories` (experiential)
3. **The system preserves both records**

This is **correct behavior**, not a defect.

### Deduplication Requirements

If deduplication is desired, it must be:

- ✅ **Explicit**: User or admin triggers it
- ✅ **Audited**: Full log of what was merged/removed
- ✅ **Intentional**: Never automatic or silent
- ✅ **Authority-preserving**: Authoritative facts cannot be removed by dedup

---

## Implementation Strategy

### Phase 1: Authority Metadata (High Priority)

#### A. Modify `create_memory` to Tag Authoritative

```python
@mcp.tool()
async def create_memory(
    fact: str, 
    key: Optional[str] = None, 
    ttl_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """Create an AUTHORITATIVE memory directly."""
    # ... existing validation ...
    
    # Construct fact with embedded authority marker
    # Option 1: Embed in fact text (simple, works with Vertex AI)
    authoritative_fact = f"[AUTHORITATIVE] {fact.strip()}"
    
    # Option 2: Use custom metadata field if Vertex AI supports it
    memory_data = {
        "fact": fact.strip(),
        "scope": scope,
        "metadata": {"authoritative": True, "source": "user_explicit"}
    }
```

#### B. Modify `generate_memories` to Tag Experiential

```python
@mcp.tool()
async def generate_memories(
    conversation: List[Dict[str, str]],
    key: Optional[str] = None,
    protect_authoritative: bool = True,  # NEW: Safety flag
    wait_for_completion: bool = True,
) -> Dict[str, Any]:
    """Generate EXPERIENTIAL memories from conversation."""
    # ... existing code ...
    
    if protect_authoritative:
        # Fetch existing authoritative memories
        existing_authoritative = await get_authoritative_memories(scope)
        # Log warning if generated memories might conflict
        # Do NOT overwrite - allow duplicates
```

### Phase 2: Retrieval Differentiation (Medium Priority)

```python
@mcp.tool()
async def retrieve_memories(
    key: Optional[str] = None, 
    search_query: Optional[str] = None, 
    top_k: int = 5,
    authority_filter: Optional[str] = None  # NEW: "authoritative" | "experiential" | None
) -> Dict[str, Any]:
    """Retrieve memories with optional authority filtering."""
    # ... existing code ...
    
    memories = []
    for retrieved in list(results):
        memory_data = format_memory(retrieved.memory)
        # Add authority classification to response
        memory_data["is_authoritative"] = is_authoritative_memory(retrieved.memory)
        memory_data["source_type"] = get_memory_source(retrieved.memory)
        memories.append(memory_data)
```

### Phase 3: Conflict Detection (Medium Priority)

```python
async def check_authority_conflict(
    new_fact: str, 
    scope: Dict[str, str],
    is_authoritative: bool
) -> Optional[Dict]:
    """
    Check if a new memory would conflict with existing authoritative memories.
    
    Returns conflict info if found, None otherwise.
    """
    if not is_authoritative:
        # Experiential memories can't overwrite authoritative
        existing = await get_authoritative_memories(scope)
        for mem in existing:
            if semantic_similarity(new_fact, mem.fact) > CONFLICT_THRESHOLD:
                return {
                    "conflict_type": "experiential_vs_authoritative",
                    "existing_memory": mem,
                    "action": "preserved_both",
                    "reason": "Authoritative memory protected"
                }
    return None
```

### Phase 4: Deduplication Tooling (Low Priority)

```python
@mcp.tool()
async def consolidate_memories(
    key: Optional[str] = None,
    dry_run: bool = True,
    preserve_authoritative: bool = True  # Always True in production
) -> Dict[str, Any]:
    """
    Consolidate and deduplicate memories (EXPLICIT operation).
    
    This is an audited, intentional operation that:
    - NEVER removes authoritative memories (unless preserve_authoritative=False)
    - Merges semantically similar experiential memories
    - Produces a full audit log
    """
    # ... implementation with full audit trail ...
```

---

## Vertex AI Memory Bank Integration

### Challenge: Custom Metadata Support

Vertex AI Memory Bank's API may not directly support arbitrary custom metadata fields. Options:

### Option 1: Embed Authority in Fact Text (Recommended for MVP)

```python
# Simple, works with any Vertex AI version
def create_authoritative_fact(fact: str) -> str:
    return f"[AUTHORITATIVE] {fact}"

def create_experiential_fact(fact: str) -> str:
    return f"[EXPERIENTIAL] {fact}"

def is_authoritative_memory(memory) -> bool:
    return memory.fact.startswith("[AUTHORITATIVE]")
```

### Option 2: Use Memory Topics for Separation

Vertex AI supports `memory_topics` in configuration:

```python
# Configure separate topics for each plane
config["customization_configs"] = [
    {
        "memory_topics": [
            {"managed_memory_topic": {"managed_topic_enum": "USER_PREFERENCES"}},
            {"managed_memory_topic": {"managed_topic_enum": "EXPLICIT_INSTRUCTIONS"}},
            # Could potentially create custom topics for authority separation
        ]
    }
]
```

### Option 3: Sidecar Database

Maintain authority metadata in a separate database:

```python
# Firestore/PostgreSQL sidecar
class MemoryAuthorityRecord:
    memory_name: str           # Vertex AI memory reference
    user_id: str
    is_authoritative: bool
    source: str                # "user_explicit" | "model_inferred"
    created_at: datetime
    tool_used: str
    conversation_ref: Optional[str]
```

---

## Failure Modes If Ignored

### At Scale, These Failures Are Catastrophic

| Failure Mode | Description | Business Impact |
|--------------|-------------|-----------------|
| **Hallucinated State** | Model believes contradictory "facts" | User confusion, support costs |
| **Preference Drift** | User preferences silently overwritten | Degraded UX, churn |
| **Non-Reproducible Behavior** | Same query, different results | Trust erosion |
| **Loss of User Trust** | "AI forgot what I told it" | Reputation damage |
| **Audit Failure** | Cannot trace memory source | Compliance violation |
| **Enterprise Rejection** | Cannot meet governance requirements | Lost revenue |

### Concrete Scenario

```
Timeline:
─────────

Day 1, 10:00 AM
  User: "Remember my billing address is 123 Main St, San Francisco"
  → create_memory stores: "Billing address: 123 Main St, San Francisco"
  
Day 3, 2:00 PM
  User: "I'm helping my friend Bob move to 456 Oak Ave, New York"
  → generate_memories infers: "User may be located in New York"
  
Day 5, 9:00 AM  
  User: "What's my billing address?"
  → System retrieves both memories
  → WITHOUT AUTHORITY SEPARATION: Which is correct?
  → WITH AUTHORITY SEPARATION: Authoritative fact (123 Main St) wins
```

---

## Recommended Implementation Roadmap

### Priority Matrix

| Priority | Task | Effort | Impact | Phase |
|----------|------|--------|--------|-------|
| 🔴 **Critical** | Add authority tagging to `create_memory` | 1 day | High | 1 |
| 🔴 **Critical** | Add authority tagging to `generate_memories` | 1 day | High | 1 |
| 🟠 **High** | Modify `generate_memories` to protect authoritative | 1 day | High | 1 |
| 🟠 **High** | Update retrieval to show authority classification | 0.5 days | Medium | 2 |
| 🟡 **Medium** | Add conflict detection logging | 1 day | Medium | 2 |
| 🟡 **Medium** | Update prompts for authority awareness | 0.5 days | Medium | 2 |
| 🟢 **Low** | Add explicit deduplication tool | 2-3 days | Low | 3 |
| 🟢 **Low** | Build authority-based analytics | 2 days | Low | 3 |

### Phase 1: Foundation (Week 1-2)

- [ ] Implement authority tagging in `create_memory`
- [ ] Implement authority tagging in `generate_memories`
- [ ] Add protection flag to prevent authoritative overwrites
- [ ] Update `formatters.py` for authority metadata

### Phase 2: Visibility (Week 3)

- [ ] Update retrieval tools to expose authority
- [ ] Add conflict detection and logging
- [ ] Update `memory_consolidation_prompt` for authority awareness
- [ ] Add authority filter parameter to search

### Phase 3: Tooling (Month 2)

- [ ] Build explicit deduplication tool with audit trail
- [ ] Add analytics for authority distribution
- [ ] Create admin tools for authority management
- [ ] Document governance procedures

---

## Appendix: Tool-to-Memory-Plane Mapping

### Complete Tool Classification

| Tool | Memory Plane | Authority | Can Modify Authoritative? |
|------|--------------|-----------|---------------------------|
| `create_memory` | Authoritative | Human | Yes (creates) |
| `delete_memory` | Authoritative | Human | Yes (deletes) |
| `generate_memories` | Experiential | Model | **No** (must protect) |
| `retrieve_memories` | Both | Read-only | No |
| `search_memories` | Both | Read-only | No |
| `fetch_memory` | Both | Read-only | No |
| `list_memories` | Both | Read-only | No |

### Future Tools (Proposed)

| Tool | Memory Plane | Authority | Purpose |
|------|--------------|-----------|---------|
| `update_memory` | Authoritative | Human | Modify existing authoritative fact |
| `consolidate_memories` | Both | Human (explicit) | Audited deduplication |
| `promote_memory` | Experiential→Authoritative | Human | Elevate belief to fact |
| `demote_memory` | Authoritative→Experiential | Human | Downgrade fact to belief |
| `audit_memories` | Both | Admin | Generate authority audit report |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-02 | Claude Opus 4.5 | Initial comprehensive analysis and design |

---

*This document establishes a critical architectural constraint for OpenReflect. The separation between authoritative and experiential memory is foundational for trust, auditability, and enterprise readiness. Implementation should prioritize the core invariant: model-generated memory must never overwrite authoritative memory without explicit human instruction.*
