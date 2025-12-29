# OpenReflect MCP Tools Guide

**Version**: 1.0  
**Date**: December 29, 2025  
**Authors**: Claude Opus 4.5 (AI Architect) in collaboration with OpenReflect Team  
**Status**: Implementation Reference  
**Related**: [AUTH_DESIGN.md](./AUTH_DESIGN.md), [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md), [ARCHITECTURE_STRATEGY.md](./ARCHITECTURE_STRATEGY.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Tool Categories](#tool-categories)
3. [Authentication Requirements](#authentication-requirements)
4. [Tool Reference](#tool-reference)
5. [Response Formats](#response-formats)
6. [Implementation Patterns](#implementation-patterns)
7. [Adding New Tools](#adding-new-tools)
8. [Migration Guide: Adding Auth to Existing Tools](#migration-guide-adding-auth-to-existing-tools)

---

## Overview

OpenReflect MCP exposes tools via the Model Context Protocol (MCP) that allow AI assistants to store, retrieve, and manage memories in Google Vertex AI Memory Bank. This document provides a complete reference for all tools, their usage, and implementation details.

### Tool Registration

All tools are registered in `src/tools.py` via the `register_tools(mcp: FastMCP)` function. This function is called during server initialization and decorates each tool with `@mcp.tool()`.

### Current Tool Count

| Category | Tools | Auth Required |
|----------|-------|---------------|
| Configuration | 1 | No (creates/loads engine) |
| Memory Generation | 1 | Yes |
| Memory Retrieval | 3 | Yes |
| Memory Management | 3 | Yes |
| **Authentication** | 4 | No (handles auth itself) |
| **Total** | **12** | |

---

## Tool Categories

### Category 1: Configuration Tools

Tools for initializing and configuring the Memory Bank connection.

| Tool | Purpose | Auth Required |
|------|---------|---------------|
| `initialize_memory_bank` | Connect to GCP project and load/create Agent Engine | No |

### Category 2: Memory Generation Tools

Tools for automatically generating memories from conversations.

| Tool | Purpose | Auth Required |
|------|---------|---------------|
| `generate_memories` | Extract memories from conversation history | Yes |

### Category 3: Memory Retrieval Tools

Tools for retrieving and searching stored memories.

| Tool | Purpose | Auth Required |
|------|---------|---------------|
| `retrieve_memories` | Get memories for a user, with optional search | Yes |
| `search_memories` | Explicit similarity search (Deep Research compatible) | Yes |
| `fetch_memory` | Get a single memory by resource name | Yes |

### Category 4: Memory Management Tools

Tools for creating, listing, and deleting memories.

| Tool | Purpose | Auth Required |
|------|---------|---------------|
| `create_memory` | Create a memory directly | Yes |
| `delete_memory` | Delete a specific memory | Yes |
| `list_memories` | List all memories in the bank | Yes |

### Category 5: Authentication Tools (NEW)

Tools for user authentication and session management.

| Tool | Purpose | Auth Required |
|------|---------|---------------|
| `connect_account` | Initiate Google OAuth flow | No |
| `connect_with_passphrase` | Authenticate with passphrase | No |
| `check_connection` | Check current auth status | No |
| `disconnect` | End authenticated session | No |

---

## Authentication Requirements

### Before Implementation

Currently, all memory tools accept a `scope` parameter directly from the client. This is **insecure** for multi-user deployment because:

1. Any client can claim any `user_id`
2. No verification of identity
3. Users could access other users' memories

### After Implementation

With authentication implemented:

1. User authenticates via OAuth or passphrase
2. Server derives `user_id` from authentication
3. Tools **ignore** client-provided scope and use authenticated `user_id`
4. Memory isolation is enforced server-side

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TOOL AUTHENTICATION FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. User calls any memory tool (e.g., create_memory)                    │
│                          │                                              │
│                          ▼                                              │
│  2. Tool checks: Is session authenticated?                              │
│            │                                                            │
│     ┌──────┴──────┐                                                     │
│     │             │                                                     │
│    YES           NO                                                     │
│     │             │                                                     │
│     ▼             ▼                                                     │
│  3a. Get         3b. Return error:                                      │
│  user_id         "Please authenticate first.                            │
│  from            Use connect_account() or                               │
│  session         connect_with_passphrase()"                             │
│     │                                                                   │
│     ▼                                                                   │
│  4. Override scope with authenticated user_id                           │
│     scope = {"user_id": session.user_id}                                │
│     │                                                                   │
│     ▼                                                                   │
│  5. Execute Vertex AI operation with server-enforced scope              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Tool Reference

### initialize_memory_bank

**Purpose**: Initialize connection to Google Cloud project and Vertex AI Memory Bank.

**Authentication**: Not required (this tool sets up the engine, not user data)

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_id` | `str` | Yes | - | Google Cloud project ID |
| `location` | `str` | No | `"us-central1"` | GCP region |
| `memory_topics` | `List[str]` | No | `None` | Topic configuration |
| `agent_engine_name` | `str` | No | `None` | Existing engine to reuse |

**Memory Topics Options**:
- `USER_PREFERENCES` - User preferences and settings
- `USER_PERSONAL_INFO` - Personal information
- `KEY_CONVERSATION_DETAILS` - Important events
- `EXPLICIT_INSTRUCTIONS` - Explicit remember/forget requests

**Returns**:

```python
# Success
{
    "success": True,
    "data": {
        "agent_engine_name": "projects/.../reasoningEngines/...",
        "project_id": "my-project",
        "location": "us-central1"
    }
}

# Error
{
    "success": False,
    "error": "Error message"
}
```

**Example Usage**:

```python
# Create new engine
await initialize_memory_bank(
    project_id="my-gcp-project",
    memory_topics=["USER_PREFERENCES", "USER_PERSONAL_INFO"]
)

# Reuse existing engine
await initialize_memory_bank(
    project_id="my-gcp-project",
    agent_engine_name="projects/my-project/locations/us-central1/reasoningEngines/12345"
)
```

**Implementation Notes**:
- If `AGENT_ENGINE_NAME` environment variable is set, server loads that engine at startup
- This tool is mainly for initial setup or dynamic reconfiguration
- In production, engine should be pre-configured via env var

**Security Hardening (Required for Production)**:

> ⚠️ **CRITICAL**: In a multi-user shared deployment, this tool must be hardened to prevent users from reconfiguring the global engine and affecting all other users.

Add this code at the **beginning** of the `initialize_memory_bank` function in `src/tools.py`:

```python
@mcp.tool()
async def initialize_memory_bank(
    project_id: str,
    location: str = "us-central1",
    memory_topics: List[str] = None,
    agent_engine_name: str = None,
) -> Dict[str, Any]:
    # SECURITY HARDENING: Prevent runtime reconfiguration in production
    # If already initialized, return current config (read-only mode)
    if app.is_ready():
        return format_success_response({
            "status": "already_initialized",
            "message": "Memory Bank is already configured. No changes made.",
            "agent_engine_name": app.agent_engine.api_resource.name,
            "project_id": app.config.project_id,
            "location": app.config.location,
            "note": "To change configuration, update AGENT_ENGINE_NAME environment variable and redeploy."
        })
    
    # ... rest of existing initialization logic (only runs if NOT initialized) ...
```

**Why This Matters**:
- Without this check, any user could call `initialize_memory_bank` and redirect all users' memory operations to a different engine
- This would either cause data loss (memories go to wrong engine) or security breach (attacker's engine receives all data)
- The hardening makes the tool "informational" in production while still allowing initial setup

---

### generate_memories

**Purpose**: Automatically extract and store memories from a conversation.

**Authentication**: **Required** - Uses authenticated user's scope

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `conversation` | `List[Dict[str, str]]` | Yes | - | Messages with `role` and `content` |
| `scope` | `Dict[str, str]` | Yes* | - | User identifier (*ignored when auth enabled) |
| `wait_for_completion` | `bool` | No | `True` | Wait for generation to finish |

**Conversation Format**:

```python
conversation = [
    {"role": "user", "content": "I'm Alice and I prefer dark mode"},
    {"role": "assistant", "content": "Nice to meet you, Alice!"},
    {"role": "user", "content": "I work as a software engineer at Acme Corp"}
]
```

**Returns**:

```python
# Success
{
    "success": True,
    "data": {
        "operation_name": "projects/.../operations/...",
        "done": True,
        "scope": {"user_id": "usr_abc123"},
        "generated_memories": [
            {"action": "CREATE", "fact": "User's name is Alice"},
            {"action": "CREATE", "fact": "User prefers dark mode"},
            {"action": "CREATE", "fact": "User works as software engineer at Acme Corp"}
        ]
    }
}
```

**Implementation Notes**:
- Vertex AI analyzes conversation and extracts memorable facts
- Deduplication is handled automatically
- Can detect updates to existing memories (action: "UPDATE")

---

### retrieve_memories

**Purpose**: Retrieve memories for the authenticated user, with optional semantic search.

**Authentication**: **Required**

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scope` | `Dict[str, str]` | Yes* | - | User identifier (*ignored when auth enabled) |
| `search_query` | `str` | No | `None` | Semantic search query |
| `top_k` | `int` | No | `5` | Max results for search |

**Returns**:

```python
# Success (no search)
{
    "success": True,
    "data": {
        "scope": {"user_id": "usr_abc123"},
        "memories_count": 3,
        "memories": [
            {
                "name": "projects/.../memories/mem_1",
                "fact": "User's name is Alice",
                "scope": {"user_id": "usr_abc123"},
                "create_time": "2025-12-29T10:30:00Z",
                "update_time": "2025-12-29T10:30:00Z"
            },
            // ... more memories
        ]
    }
}

# Success (with search)
{
    "success": True,
    "data": {
        "scope": {"user_id": "usr_abc123"},
        "memories_count": 2,
        "memories": [
            {
                "name": "projects/.../memories/mem_1",
                "fact": "User prefers dark mode in all applications",
                "similarity_score": 0.92,
                // ...
            }
        ]
    }
}
```

**Example Usage**:

```python
# Get all memories
await retrieve_memories(scope={"user_id": "alice123"})

# Semantic search
await retrieve_memories(
    scope={"user_id": "alice123"},
    search_query="What are the user's UI preferences?",
    top_k=3
)
```

---

### search_memories

**Purpose**: Explicit semantic search tool (compatibility alias for Deep Research).

**Authentication**: **Required**

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scope` | `Dict[str, str]` | Yes* | - | User identifier |
| `search_query` | `str` | Yes | - | Search query |
| `top_k` | `int` | No | `5` | Max results |

**Implementation**: Calls `retrieve_memories` internally with `search_query` parameter.

---

### fetch_memory

**Purpose**: Retrieve a single memory by its full resource name.

**Authentication**: **Required** (should verify memory belongs to authenticated user)

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `memory_name` | `str` | Yes | - | Full memory resource name |

**Returns**:

```python
{
    "success": True,
    "data": {
        "memory": {
            "name": "projects/.../memories/mem_123",
            "fact": "User's favorite color is blue",
            "scope": {"user_id": "usr_abc123"},
            "create_time": "2025-12-29T10:30:00Z",
            "update_time": "2025-12-29T10:30:00Z"
        }
    }
}
```

**Security Note**: Implementation should verify the memory's scope matches the authenticated user to prevent cross-user access.

---

### create_memory

**Purpose**: Directly create a memory for the authenticated user.

**Authentication**: **Required**

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `fact` | `str` | Yes | - | The information to remember |
| `scope` | `Dict[str, str]` | Yes* | - | User identifier (*ignored when auth enabled) |
| `ttl_seconds` | `int` | No | `None` | Time-to-live in seconds |

**Returns**:

```python
{
    "success": True,
    "data": {
        "memory": {
            "name": "projects/.../memories/mem_456",
            "fact": "User has a meeting with Bob on Friday",
            "scope": {"user_id": "usr_abc123"},
            "create_time": "2025-12-29T14:00:00Z",
            "expire_time": "2025-12-30T14:00:00Z"  // If TTL was set
        }
    }
}
```

**Example Usage**:

```python
# Permanent memory
await create_memory(
    fact="User's favorite programming language is Python",
    scope={"user_id": "alice123"}
)

# Temporary memory (expires in 24 hours)
await create_memory(
    fact="User has a dentist appointment tomorrow at 2pm",
    scope={"user_id": "alice123"},
    ttl_seconds=86400
)
```

---

### delete_memory

**Purpose**: Delete a specific memory by resource name.

**Authentication**: **Required** (should verify ownership)

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `memory_name` | `str` | Yes | - | Full memory resource name |

**Returns**:

```python
{
    "success": True,
    "data": {
        "deleted": "projects/.../memories/mem_123"
    }
}
```

**Security Note**: Implementation should verify the memory belongs to the authenticated user before deletion.

---

### list_memories

**Purpose**: List all memories in the Memory Bank (for current user when auth enabled).

**Authentication**: **Required**

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_size` | `int` | No | `50` | Memories per page |

**Returns**:

```python
{
    "success": True,
    "data": {
        "count": 15,
        "memories": [
            {
                "name": "projects/.../memories/mem_1",
                "fact": "...",
                "scope": {"user_id": "usr_abc123"},
                // ...
            },
            // ... more memories
        ]
    }
}
```

**Implementation Note**: When auth is enabled, this should filter to only the authenticated user's memories, not all memories in the engine.

---

### connect_account (NEW)

**Purpose**: Initiate Google OAuth flow for authentication.

**Authentication**: Not required (this IS the auth mechanism)

**Parameters**: None

**Returns**:

```python
# Not yet authenticated
{
    "status": "auth_required",
    "auth_url": "https://openreflect.run.app/oauth/authorize?session_id=sess_123",
    "message": "Please click the link to sign in with Google and connect your memory bank."
}

# Already authenticated
{
    "status": "already_connected",
    "email": "alice@gmail.com",
    "auth_method": "oauth",
    "message": "Your account is already connected!"
}
```

**User Flow**:
1. AI presents the auth_url to the user
2. User clicks link → Google sign-in popup
3. User consents → redirected back to callback
4. Session is now authenticated
5. Subsequent tool calls use authenticated identity

---

### connect_with_passphrase (NEW)

**Purpose**: Authenticate using a passphrase instead of OAuth.

**Authentication**: Not required (this IS the auth mechanism)

**Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `passphrase` | `str` | Yes | - | User's passphrase (min 4 chars) |

**Returns**:

```python
{
    "status": "connected",
    "message": "Connected to your memory bank!",
    "tip": "Use this same passphrase in other AI assistants to access your memories.",
    "upgrade_hint": "For easier access, you can link your Google account with connect_account()."
}
```

**Security Properties**:
- Passphrase is normalized (lowercase, trimmed)
- Combined with server-side secret before hashing
- Same passphrase → same user_id (deterministic)
- Passphrase is never stored

---

### check_connection (NEW)

**Purpose**: Check current authentication status.

**Authentication**: Not required

**Parameters**: None

**Returns**:

```python
# Connected
{
    "status": "connected",
    "user_id": "usr_abc123",
    "email": "alice@gmail.com",  // null if passphrase auth
    "auth_method": "oauth",  // or "passphrase"
    "connected_since": "2025-12-29T10:30:00Z"
}

# Not connected
{
    "status": "not_connected",
    "message": "You're not connected. Use connect_account() or connect_with_passphrase() to connect."
}
```

---

### disconnect (NEW)

**Purpose**: End the authenticated session.

**Authentication**: Not required

**Parameters**: None

**Returns**:

```python
{
    "status": "disconnected",
    "message": "Disconnected from your memory bank. Your memories are safe and you can reconnect anytime."
}
```

---

## Response Formats

All tools return responses in a consistent format using formatter functions from `src/formatters.py`.

### Success Response

```python
def format_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "success": True,
        "data": data
    }
```

### Error Response

```python
def format_error_response(error: str) -> Dict[str, Any]:
    return {
        "success": False,
        "error": error
    }
```

### Memory Format

```python
def format_memory(memory) -> Dict[str, Any]:
    return {
        "name": memory.name,
        "fact": memory.fact,
        "scope": dict(memory.scope) if memory.scope else {},
        "create_time": memory.create_time.isoformat() if memory.create_time else None,
        "update_time": memory.update_time.isoformat() if memory.update_time else None,
        "expire_time": memory.expire_time.isoformat() if hasattr(memory, 'expire_time') and memory.expire_time else None
    }
```

---

## Implementation Patterns

### Pattern 1: Auth-Required Tool (With Scope Override)

Use this pattern for tools that need user-specific data and should override client-provided scope:

```python
@mcp.tool()
async def example_auth_tool(
    some_param: str,
    scope: Dict[str, str],  # Keep for API compatibility, but will be overridden
) -> Dict[str, Any]:
    """Tool that requires authentication and uses server-enforced scope."""
    
    # Step 1: Check if Memory Bank is initialized
    if not app.is_ready():
        return format_error_response(
            "Memory Bank not initialized. Call initialize_memory_bank first."
        )
    
    # Step 2: Require authentication
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    # Step 3: Override scope with authenticated user_id (CRITICAL!)
    scope = {"user_id": session.user_id}
    
    # Step 4: Execute operation with server-enforced scope
    try:
        result = app.client.agent_engines.some_operation(
            name=app.agent_engine.api_resource.name,
            scope=scope,
            # ... other params
        )
        return format_success_response({"result": result})
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return format_error_response(str(e))
```

### Pattern 2: Auth-Optional Tool

Use this pattern for tools that work differently based on auth status:

```python
@mcp.tool()
async def example_optional_auth_tool() -> Dict[str, Any]:
    """Tool that works with or without authentication."""
    
    session = get_session_if_authenticated()
    
    if session:
        # Authenticated path
        return format_success_response({
            "mode": "authenticated",
            "user_id": session.user_id
        })
    else:
        # Unauthenticated path
        return format_success_response({
            "mode": "anonymous",
            "message": "Connect your account for personalized experience"
        })
```

### Pattern 3: Ownership Verification

Use this pattern for tools that access specific resources and need to verify ownership:

```python
@mcp.tool()
async def example_resource_tool(memory_name: str) -> Dict[str, Any]:
    """Tool that accesses a specific resource and verifies ownership."""
    
    if not app.is_ready():
        return format_error_response("Memory Bank not initialized.")
    
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    try:
        # Fetch the resource
        memory = app.client.agent_engines.get_memory(name=memory_name)
        
        # Verify ownership (CRITICAL for security!)
        memory_user_id = memory.scope.get("user_id") if memory.scope else None
        if memory_user_id != session.user_id:
            return format_error_response(
                "Access denied: This memory belongs to another user."
            )
        
        # Resource belongs to authenticated user, proceed
        return format_success_response({"memory": format_memory(memory)})
        
    except Exception as e:
        logger.error(f"Failed to fetch memory: {e}")
        return format_error_response(str(e))
```

---

## Adding New Tools

### Step 1: Define the Tool

Add the tool function inside `register_tools()` in `src/tools.py`:

```python
@mcp.tool()
async def my_new_tool(
    param1: str,
    param2: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Short description of what the tool does.
    
    Longer description with usage details.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (optional)
    
    Returns:
        Description of return value
    
    Example:
        await my_new_tool(param1="value", param2=42)
    """
    # Implementation here
    pass
```

### Step 2: Apply Appropriate Auth Pattern

Choose from the patterns above based on whether the tool:
- Requires authentication
- Accesses user-specific data
- Needs ownership verification

### Step 3: Use Standard Response Formats

Always use `format_success_response()` and `format_error_response()` for consistency.

### Step 4: Add Logging

```python
logger.info(f"Performed action for user {session.user_id}")
logger.error(f"Failed to perform action: {e}")
```

### Step 5: Update Documentation

Add the new tool to this guide with:
- Purpose
- Authentication requirement
- Parameters table
- Returns format
- Example usage

---

## Migration Guide: Adding Auth to Existing Tools

This section provides exact code changes needed to add authentication to the 8 existing memory tools.

### Prerequisites

Before migrating tools, ensure these components exist (see [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)):

1. `src/auth.py` with `require_auth()` and `get_current_session_id()` functions
2. `src/sessions.py` with `SessionState` dataclass and `sessions` dict
3. Session context propagation in `server_http.py`

### Migration: generate_memories

**Before** (lines 122-207 in tools.py):

```python
@mcp.tool()
async def generate_memories(
    conversation: List[Dict[str, str]],
    scope: Dict[str, str],
    wait_for_completion: bool = True,
) -> Dict[str, Any]:
    if not app.is_ready():
        return format_error_response(...)
    
    if error := validate_scope(scope):
        return format_error_response(error)
    # ... uses client-provided scope
```

**After**:

```python
@mcp.tool()
async def generate_memories(
    conversation: List[Dict[str, str]],
    scope: Dict[str, str],  # Kept for API compatibility, will be overridden
    wait_for_completion: bool = True,
) -> Dict[str, Any]:
    if not app.is_ready():
        return format_error_response(
            "Memory Bank not initialized. Call initialize_memory_bank first."
        )
    
    # NEW: Require authentication
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    # NEW: Override scope with authenticated user_id
    scope = {"user_id": session.user_id}
    
    if error := validate_conversation(conversation):
        return format_error_response(error)
    
    # ... rest unchanged, now uses server-enforced scope
```

### Migration: retrieve_memories

**After**:

```python
@mcp.tool()
async def retrieve_memories(
    scope: Dict[str, str],
    search_query: Optional[str] = None,
    top_k: int = 5
) -> Dict[str, Any]:
    if not app.is_ready():
        return format_error_response(
            "Memory Bank not initialized. Call initialize_memory_bank first."
        )
    
    # NEW: Require authentication
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    # NEW: Override scope with authenticated user_id
    scope = {"user_id": session.user_id}
    
    # ... rest unchanged
```

### Migration: create_memory

**After**:

```python
@mcp.tool()
async def create_memory(
    fact: str,
    scope: Dict[str, str],
    ttl_seconds: Optional[int] = None
) -> Dict[str, Any]:
    if not app.is_ready():
        return format_error_response(
            "Memory Bank not initialized. Call initialize_memory_bank first."
        )
    
    # NEW: Require authentication
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    # NEW: Override scope with authenticated user_id
    scope = {"user_id": session.user_id}
    
    if error := validate_memory_fact(fact):
        return format_error_response(error)
    
    # ... rest unchanged
```

### Migration: delete_memory

**After** (with ownership verification):

```python
@mcp.tool()
async def delete_memory(memory_name: str) -> Dict[str, Any]:
    if not app.is_ready():
        return format_error_response(
            "Memory Bank not initialized. Call initialize_memory_bank first."
        )
    
    # NEW: Require authentication
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    try:
        # NEW: Verify ownership before deletion
        memory = app.client.agent_engines.get_memory(name=memory_name)
        memory_user_id = memory.scope.get("user_id") if memory.scope else None
        
        if memory_user_id != session.user_id:
            return format_error_response(
                "Access denied: You can only delete your own memories."
            )
        
        app.client.agent_engines.delete_memory(name=memory_name)
        logger.info(f"Deleted memory: {memory_name} by user {session.user_id}")
        
        return format_success_response({"deleted": memory_name})
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        return format_error_response(str(e))
```

### Migration: fetch_memory

**After** (with ownership verification):

```python
@mcp.tool()
async def fetch_memory(memory_name: str) -> Dict[str, Any]:
    if not app.is_ready():
        return format_error_response(
            "Memory Bank not initialized. Call initialize_memory_bank first."
        )
    
    # NEW: Require authentication
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    try:
        memory = app.client.agent_engines.get_memory(name=memory_name)
        
        # NEW: Verify ownership
        memory_user_id = memory.scope.get("user_id") if memory.scope else None
        if memory_user_id != session.user_id:
            return format_error_response(
                "Access denied: This memory belongs to another user."
            )
        
        return format_success_response({"memory": format_memory(memory)})
    except Exception as e:
        logger.error(f"Failed to fetch memory: {e}")
        return format_error_response(str(e))
```

### Migration: list_memories

**After** (filtered to user's memories):

```python
@mcp.tool()
async def list_memories(page_size: int = 50) -> Dict[str, Any]:
    if not app.is_ready():
        return format_error_response(
            "Memory Bank not initialized. Call initialize_memory_bank first."
        )
    
    # NEW: Require authentication
    try:
        session = await require_auth()
    except AuthenticationRequired as e:
        return format_error_response(str(e))
    
    try:
        # Use retrieve_memories with user's scope instead of list_memories
        # This ensures we only get the authenticated user's memories
        results = app.client.agent_engines.retrieve_memories(
            name=app.agent_engine.api_resource.name,
            scope={"user_id": session.user_id}
        )
        
        memories = []
        for retrieved in list(results):
            memories.append(format_memory(retrieved.memory))
        
        logger.info(f"Listed {len(memories)} memories for user {session.user_id}")
        
        return format_success_response({
            "count": len(memories),
            "memories": memories
        })
    except Exception as e:
        logger.error(f"Failed to list memories: {e}")
        return format_error_response(str(e))
```

### Migration: search_memories

This tool calls `retrieve_memories` internally, so once `retrieve_memories` is migrated, `search_memories` is automatically auth-aware.

### Tools That DON'T Need Migration

- `initialize_memory_bank` - This configures the engine, not user data. No auth needed.

---

## Imports Required for Auth

Add these imports to `src/tools.py`:

```python
from .auth import require_auth, AuthenticationRequired
```

---

## Summary

| Tool | Auth Migration | Ownership Check |
|------|----------------|-----------------|
| `initialize_memory_bank` | ❌ Not needed | ❌ Not needed |
| `generate_memories` | ✅ Add auth, override scope | ❌ Not needed |
| `retrieve_memories` | ✅ Add auth, override scope | ❌ Not needed |
| `search_memories` | ✅ Inherits from retrieve_memories | ❌ Not needed |
| `fetch_memory` | ✅ Add auth | ✅ Verify ownership |
| `create_memory` | ✅ Add auth, override scope | ❌ Not needed |
| `delete_memory` | ✅ Add auth | ✅ Verify ownership |
| `list_memories` | ✅ Add auth, filter by user | ❌ Not needed |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-29 | Claude Opus 4.5 | Initial comprehensive tools guide |

---

*This document should be updated whenever tools are added, modified, or removed.*
