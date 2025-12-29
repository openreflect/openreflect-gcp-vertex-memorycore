# OpenReflect Authentication Design Document

**Version**: 1.0  
**Date**: December 29, 2025  
**Authors**: Claude Opus 4.5 (AI Architect) in collaboration with OpenReflect Team  
**Status**: Design Specification  
**Related**: [ARCHITECTURE_STRATEGY.md](./ARCHITECTURE_STRATEGY.md), [SECURITY.md](./SECURITY.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Authentication Strategy Overview](#authentication-strategy-overview)
3. [OAuth 2.0 Implementation](#oauth-20-implementation)
4. [Passphrase Hash Fallback](#passphrase-hash-fallback)
5. [Session Management](#session-management)
6. [User Identity Model](#user-identity-model)
7. [Client-Specific Flows](#client-specific-flows)
8. [Implementation Reference](#implementation-reference)
9. [Security Considerations](#security-considerations)
10. [Migration & Account Linking](#migration--account-linking)

---

## Executive Summary

This document defines the authentication architecture for OpenReflect's multi-user MCP service. The design enables secure user identification across multiple AI clients (ChatGPT, Claude Desktop, Gemini) while maintaining a seamless user experience.

### Core Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AUTHENTICATION STRATEGY                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PRIMARY: OAuth 2.0 (Google/GCP Identity Platform)                      │
│  ─────────────────────────────────────────────────────────────────────  │
│  • ChatGPT Web: Native OAuth popup (like Gmail MCP)                     │
│  • Claude Desktop: OAuth redirect flow                                  │
│  • Strong identity, no user-managed secrets                             │
│  • Familiar UX pattern for users                                        │
│                                                                         │
│  FALLBACK: Passphrase Hash                                              │
│  ─────────────────────────────────────────────────────────────────────  │
│  • Clients that don't support OAuth                                     │
│  • Offline/air-gapped scenarios                                         │
│  • "Quick connect" without full auth                                    │
│  • Same user_id derivation = same memories                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **OAuth-First**: Use Google OAuth as the primary authentication method
2. **Graceful Fallback**: Passphrase hash for clients that can't do OAuth
3. **Deterministic Identity**: Same input → same user_id → same memories
4. **Client-Agnostic**: Works identically across ChatGPT, Claude, Gemini
5. **Zero External Navigation** (where possible): Authentication inline in chat

---

## Authentication Strategy Overview

### Why Two Methods?

| Scenario | OAuth | Passphrase Hash |
|----------|-------|-----------------|
| ChatGPT Web | ✅ Native popup support | Backup |
| Claude Desktop | ✅ Redirect flow | Backup |
| Gemini | ✅ Expected support | Backup |
| Offline/Air-gapped | ❌ Requires internet | ✅ Works offline |
| Enterprise SSO | ✅ Can integrate | ❌ Not applicable |
| Quick demo/testing | Slower (redirect) | ✅ Instant |

### Authentication Decision Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    USER AUTHENTICATION DECISION                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User: "Remember that I like dark mode"                                 │
│                          │                                              │
│                          ▼                                              │
│  MCP Server: Is this session authenticated?                             │
│            │                                                            │
│     ┌──────┴──────┐                                                     │
│     │             │                                                     │
│    YES           NO                                                     │
│     │             │                                                     │
│     ▼             ▼                                                     │
│  Proceed     AI: "I'd like to save this to your memory bank.            │
│  with            Would you like to:                                     │
│  operation       1. Sign in with Google (recommended)                   │
│                  2. Use a passphrase"                                   │
│                          │                                              │
│            ┌─────────────┴─────────────┐                                │
│            │                           │                                │
│            ▼                           ▼                                │
│     "Sign in with Google"       "Use passphrase xyz"                    │
│            │                           │                                │
│            ▼                           ▼                                │
│     OAuth flow                  Hash derivation                         │
│     (popup/redirect)            (inline)                                │
│            │                           │                                │
│            └───────────┬───────────────┘                                │
│                        │                                                │
│                        ▼                                                │
│              Session now has user_id                                    │
│              All memory ops scoped                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## OAuth 2.0 Implementation

### Provider Recommendation

| Provider | Pros | Cons | Verdict |
|----------|------|------|---------|
| **GCP Identity Platform** | Native Google, scales with your infra, free tier generous | More setup than Firebase | ✅ **Best for production** |
| **Firebase Auth** | Same backend as Identity Platform, easier SDK, better docs | Slight vendor lock-in | ✅ **Best for fast start** |
| **Cloudflare Access** | Already using Cloudflare? Integrates well | More complex OAuth, less flexible | ⚠️ If already invested |
| **Auth0** | Feature-rich, great DX | Cost scales with users, another vendor | ⚠️ If team knows it |
| **Roll your own** | Full control | Security liability, maintenance burden | ❌ Don't |

**Recommendation**: Start with **Firebase Auth** for MVP, migrate to **GCP Identity Platform** if needed. They share the same backend infrastructure.

### OAuth Flow for ChatGPT Web

This flow mirrors how Gmail, Tripadvisor, and other MCPs work in ChatGPT:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     OAUTH FLOW (ChatGPT Web)                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. User enables OpenReflect MCP in ChatGPT                              │
│                          │                                               │
│                          ▼                                               │
│  2. First tool call → MCP returns:                                       │
│     { "auth_required": true, "auth_url": "https://..." }                 │
│                          │                                               │
│                          ▼                                               │
│  3. ChatGPT shows OAuth popup/redirect                                   │
│     ┌────────────────────────────────────┐                               │
│     │  🔐 Sign in with Google            │                               │
│     │                                    │                               │
│     │  OpenReflect wants to:             │                               │
│     │  • Know who you are on Google      │                               │
│     │  • Access your email address       │                               │
│     │                                    │                               │
│     │  [Allow]  [Deny]                   │                               │
│     └────────────────────────────────────┘                               │
│                          │                                               │
│                          ▼                                               │
│  4. Google redirects to OpenReflect callback:                            │
│     https://openreflect.run.app/oauth/callback?code=xxx&state=yyy        │
│                          │                                               │
│                          ▼                                               │
│  5. Server exchanges code for tokens, extracts:                          │
│     • email: alice@gmail.com                                             │
│     • sub: Google user ID (stable, never changes)                        │
│                          │                                               │
│                          ▼                                               │
│  6. Server derives user_id and binds to session:                         │
│     user_id = "usr_" + hash(google_sub + secret)[:16]                    │
│                          │                                               │
│                          ▼                                               │
│  7. All subsequent MCP calls include session → user_id                   │
│     Memory operations automatically scoped to user                       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### OAuth Endpoints

#### Authorization Endpoint

```
GET /oauth/authorize?session_id={session_id}
```

Initiates the OAuth flow by redirecting to Google's authorization server.

**Parameters:**
- `session_id`: The MCP session ID to bind after successful auth

**Response:** HTTP 302 redirect to Google OAuth

#### Callback Endpoint

```
GET /oauth/callback?code={auth_code}&state={encoded_session}
```

Handles Google's OAuth callback after user consents.

**Parameters:**
- `code`: Authorization code from Google
- `state`: Encoded session_id for binding

**Response:** HTML page confirming success (auto-closes popup)

### OAuth Configuration

Required environment variables:

```bash
# Google OAuth credentials (from Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# OAuth redirect URI (must match Cloud Console config)
OAUTH_REDIRECT_URI=https://openreflect.run.app/oauth/callback

# Identity derivation secret (never expose)
IDENTITY_SECRET=your-random-32-byte-secret
```

### Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Create **OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Name: `OpenReflect MCP`
   - Authorized redirect URIs: `https://openreflect.run.app/oauth/callback`
4. Note the **Client ID** and **Client Secret**
5. Configure OAuth consent screen:
   - App name: `OpenReflect`
   - User support email: your email
   - Scopes: `email`, `profile`, `openid`

---

## Passphrase Hash Fallback

### When to Use

- Client doesn't support OAuth popups/redirects
- User prefers not to link Google account
- Quick demo or testing scenarios
- Offline or air-gapped environments

### Hash Derivation Algorithm

```python
import hashlib

def derive_user_id(passphrase: str, identity_secret: str) -> str:
    """
    Derive a deterministic user_id from a passphrase.
    
    Same passphrase + same secret = same user_id (always)
    
    Args:
        passphrase: User-provided passphrase (case-insensitive)
        identity_secret: Server-side secret (from env var)
    
    Returns:
        Deterministic user_id: "usr_" + 16 hex chars
    """
    # Normalize: lowercase, strip whitespace
    normalized = passphrase.lower().strip()
    
    # Hash with secret to prevent rainbow table attacks
    hash_input = f"{normalized}:{identity_secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    
    # Take first 8 bytes (16 hex chars) for user_id
    user_id = f"usr_{hash_bytes[:8].hex()}"
    
    return user_id
```

### Security Properties

| Property | Status | Notes |
|----------|--------|-------|
| Deterministic | ✅ | Same input = same output |
| Server-side secret | ✅ | Passphrase alone insufficient |
| Case-insensitive | ✅ | Reduces user error |
| No storage of passphrase | ✅ | Only hash is derived |
| Rainbow table resistant | ✅ | Server secret acts as salt |

### Passphrase Guidelines for Users

Communicate to users:
- Use the **same passphrase** across all AI assistants
- Longer is better (but short is fine for personal use)
- **Don't share** your passphrase (anyone with it can access your memories)
- Consider **linking Google** for stronger security

---

## Session Management

### Session Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SESSION LIFECYCLE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. SSE Connection Established                                          │
│     → Server generates: session_id = uuid4()                            │
│     → Session state: UNAUTHENTICATED                                    │
│                                                                         │
│  2. Authentication (OAuth or Passphrase)                                │
│     → Server binds: session_id → user_id                                │
│     → Session state: AUTHENTICATED                                      │
│     → Optional: Store email, tier, preferences                          │
│                                                                         │
│  3. Normal Operation                                                    │
│     → All tool calls lookup user_id from session_id                     │
│     → Memory operations use scope = {"user_id": user_id}                │
│                                                                         │
│  4. Session End (SSE disconnect)                                        │
│     → Clean up in-memory session state                                  │
│     → User must re-authenticate on reconnect                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Session Storage

For MVP, sessions are stored **in-memory per instance**:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

@dataclass
class SessionState:
    session_id: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    auth_method: Optional[str] = None  # "oauth" or "passphrase"
    authenticated_at: Optional[datetime] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

# In-memory session store (per Cloud Run instance)
sessions: Dict[str, SessionState] = {}
```

### Session Persistence (Future)

For production with multiple Cloud Run instances, consider:

| Option | Pros | Cons |
|--------|------|------|
| **Redis (Memorystore)** | Fast, native GCP | Additional cost |
| **Firestore** | Serverless, scales | Higher latency |
| **Sticky sessions** | No external store | Limited scalability |
| **JWT in cookie** | Stateless | Larger payloads |

**Recommendation**: Start with in-memory, add Redis when scaling requires it.

---

## User Identity Model

### User ID Derivation

Both OAuth and passphrase produce the same format of user_id:

```python
# OAuth: Derive from Google's stable user ID (sub claim)
def derive_user_id_from_google(google_sub: str, secret: str) -> str:
    hash_input = f"google:{google_sub}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    return f"usr_{hash_bytes[:8].hex()}"

# Passphrase: Derive from user-provided passphrase
def derive_user_id_from_passphrase(passphrase: str, secret: str) -> str:
    normalized = passphrase.lower().strip()
    hash_input = f"passphrase:{normalized}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    return f"usr_{hash_bytes[:8].hex()}"
```

### User Record (Database)

```python
@dataclass
class User:
    user_id: str                    # Primary key: "usr_abc123def456"
    
    # Identity sources (can have multiple)
    google_sub: Optional[str]       # Google's stable user ID
    passphrase_hash: Optional[str]  # Hash of passphrase (for verification)
    email: Optional[str]            # From OAuth or user-provided
    
    # Account metadata
    tier: str = "free"              # "free", "pro", "enterprise"
    created_at: datetime = None
    last_active: datetime = None
    
    # Usage tracking
    memory_count: int = 0
    monthly_operations: int = 0
```

### Scope Format for Memory Operations

```python
# Standard scope for all memory operations
def get_scope_for_user(user_id: str) -> Dict[str, str]:
    return {"user_id": user_id}

# Usage in tools
@mcp.tool()
async def create_memory(fact: str, ...):
    session_id = get_current_session_id()
    session = sessions.get(session_id)
    
    if not session or not session.is_authenticated:
        return {"error": "Please authenticate first", "auth_required": True}
    
    scope = get_scope_for_user(session.user_id)
    # ... create memory with scope
```

---

## Client-Specific Flows

### ChatGPT Web

**Best experience** - native OAuth popup support (like Gmail, Tripadvisor MCPs).

```
User enables MCP → First tool call → OAuth popup → Authenticated
```

The user sees a familiar Google sign-in popup, consents, and is immediately authenticated.

### Claude Desktop

**Good experience** - OAuth redirect flow with browser.

```
User calls connect_account → AI provides link → User clicks → Browser opens
→ Google auth → Callback → Return to Claude Desktop
```

Configuration in `claude_desktop_config.json` can also include a pre-configured token:

```json
{
  "mcpServers": {
    "openreflect": {
      "command": "...",
      "env": {
        "OPENREFLECT_USER_TOKEN": "pre-authenticated-token"
      }
    }
  }
}
```

### Gemini

**Expected** - likely similar to ChatGPT with OAuth popup support.

### Fallback (Any Client)

For clients without OAuth support or users who prefer passphrase:

```
User: "Remember my favorite color is blue"

AI: "I'd like to save this to your memory bank. Please provide your 
     passphrase to connect (or say 'sign in with Google')."

User: "my-secret-phrase"

AI: "Connected! I'll remember that your favorite color is blue."
```

---

## Implementation Reference

### OAuth Router (FastAPI)

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
import httpx
import os
import json
import base64

oauth_router = APIRouter(prefix="/oauth", tags=["oauth"])

# Configuration
CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = os.environ.get(
    "OAUTH_REDIRECT_URI", 
    "https://openreflect.run.app/oauth/callback"
)
IDENTITY_SECRET = os.environ["IDENTITY_SECRET"]

def encode_state(session_id: str) -> str:
    """Encode session_id for OAuth state parameter."""
    return base64.urlsafe_b64encode(
        json.dumps({"session_id": session_id}).encode()
    ).decode()

def decode_state(state: str) -> str:
    """Decode session_id from OAuth state parameter."""
    data = json.loads(base64.urlsafe_b64decode(state))
    return data["session_id"]

@oauth_router.get("/authorize")
async def authorize(session_id: str):
    """
    Initiate OAuth flow.
    
    ChatGPT/Claude redirects user here when auth is needed.
    """
    if not session_id:
        raise HTTPException(400, "session_id required")
    
    state = encode_state(session_id)
    
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        "response_type=code&"
        "scope=email%20profile%20openid&"
        "access_type=offline&"
        f"state={state}"
    )
    
    return RedirectResponse(auth_url)

@oauth_router.get("/callback")
async def callback(code: str, state: str):
    """
    Handle OAuth callback from Google.
    
    Exchanges code for tokens, extracts user info, binds session.
    """
    try:
        session_id = decode_state(state)
    except Exception:
        raise HTTPException(400, "Invalid state parameter")
    
    # Exchange authorization code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(500, "Failed to exchange code for tokens")
        
        tokens = token_response.json()
    
    # Get user info from Google
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        
        if userinfo_response.status_code != 200:
            raise HTTPException(500, "Failed to get user info")
        
        user_info = userinfo_response.json()
    
    # Derive stable user_id from Google's sub (user ID)
    google_sub = user_info["id"]
    user_id = derive_user_id_from_google(google_sub, IDENTITY_SECRET)
    email = user_info.get("email")
    
    # Bind session to user
    await bind_session_to_user(
        session_id=session_id,
        user_id=user_id,
        email=email,
        auth_method="oauth",
        google_sub=google_sub
    )
    
    # Return success page
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OpenReflect - Connected!</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 2rem;
            }}
            .checkmark {{
                font-size: 4rem;
                margin-bottom: 1rem;
            }}
            h1 {{
                margin-bottom: 0.5rem;
            }}
            p {{
                color: #a0a0a0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="checkmark">✓</div>
            <h1>Connected to OpenReflect!</h1>
            <p>Signed in as {email or 'User'}</p>
            <p>You can close this window and return to your AI assistant.</p>
        </div>
        <script>
            // Auto-close after 3 seconds
            setTimeout(() => window.close(), 3000);
        </script>
    </body>
    </html>
    """)

async def bind_session_to_user(
    session_id: str,
    user_id: str,
    email: Optional[str] = None,
    auth_method: str = "oauth",
    google_sub: Optional[str] = None
):
    """Bind an MCP session to an authenticated user."""
    from datetime import datetime
    
    # Update session state
    if session_id in sessions:
        sessions[session_id].user_id = user_id
        sessions[session_id].email = email
        sessions[session_id].auth_method = auth_method
        sessions[session_id].authenticated_at = datetime.utcnow()
    else:
        sessions[session_id] = SessionState(
            session_id=session_id,
            user_id=user_id,
            email=email,
            auth_method=auth_method,
            authenticated_at=datetime.utcnow()
        )
    
    # Optionally: Create/update user record in database
    # await upsert_user(user_id, email, google_sub)
```

### Authentication Tools (MCP)

```python
from typing import Dict, Any, Optional

@mcp.tool()
async def connect_account() -> Dict[str, Any]:
    """
    Connect your Google account to access your memories across all AI assistants.
    
    This opens a Google sign-in page. Once you sign in, your memories will be
    accessible from ChatGPT, Claude, Gemini, and any other AI with OpenReflect.
    
    Returns:
        Connection status and instructions
    """
    session_id = get_current_session_id()
    
    # Check if already authenticated
    session = sessions.get(session_id)
    if session and session.is_authenticated:
        return {
            "status": "already_connected",
            "email": session.email,
            "auth_method": session.auth_method,
            "message": "Your account is already connected!"
        }
    
    # Generate auth URL
    auth_url = f"https://openreflect.run.app/oauth/authorize?session_id={session_id}"
    
    return {
        "status": "auth_required",
        "auth_url": auth_url,
        "message": "Please click the link to sign in with Google and connect your memory bank."
    }

@mcp.tool()
async def connect_with_passphrase(passphrase: str) -> Dict[str, Any]:
    """
    Connect using a passphrase instead of Google sign-in.
    
    Use the same passphrase across all AI assistants to access the same memories.
    This is useful if you prefer not to use Google sign-in.
    
    Args:
        passphrase: A memorable phrase (case-insensitive, will be normalized)
    
    Returns:
        Connection status
    
    Example:
        connect_with_passphrase("my secret memory phrase")
    """
    session_id = get_current_session_id()
    
    # Validate passphrase
    if not passphrase or len(passphrase.strip()) < 4:
        return {
            "status": "error",
            "message": "Please provide a passphrase with at least 4 characters."
        }
    
    # Derive user_id from passphrase
    user_id = derive_user_id_from_passphrase(passphrase, IDENTITY_SECRET)
    
    # Bind session to user
    await bind_session_to_user(
        session_id=session_id,
        user_id=user_id,
        email=None,
        auth_method="passphrase"
    )
    
    return {
        "status": "connected",
        "message": "Connected to your memory bank!",
        "tip": "Use this same passphrase in other AI assistants to access your memories.",
        "upgrade_hint": "For easier access, you can link your Google account with connect_account()."
    }

@mcp.tool()
async def check_connection() -> Dict[str, Any]:
    """
    Check your current connection status.
    
    Returns:
        Current authentication status and user info
    """
    session_id = get_current_session_id()
    session = sessions.get(session_id)
    
    if not session or not session.is_authenticated:
        return {
            "status": "not_connected",
            "message": "You're not connected. Use connect_account() or connect_with_passphrase() to connect."
        }
    
    return {
        "status": "connected",
        "user_id": session.user_id,
        "email": session.email,
        "auth_method": session.auth_method,
        "connected_since": session.authenticated_at.isoformat() if session.authenticated_at else None
    }

@mcp.tool()
async def disconnect() -> Dict[str, Any]:
    """
    Disconnect from your memory bank for this session.
    
    Your memories remain safe - you can reconnect anytime.
    
    Returns:
        Disconnection confirmation
    """
    session_id = get_current_session_id()
    session = sessions.get(session_id)
    
    if session:
        session.user_id = None
        session.email = None
        session.auth_method = None
        session.authenticated_at = None
    
    return {
        "status": "disconnected",
        "message": "Disconnected from your memory bank. Your memories are safe and you can reconnect anytime."
    }
```

### Helper Functions

```python
import hashlib
from typing import Optional

def derive_user_id_from_google(google_sub: str, secret: str) -> str:
    """Derive user_id from Google's stable user ID."""
    hash_input = f"google:{google_sub}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    return f"usr_{hash_bytes[:8].hex()}"

def derive_user_id_from_passphrase(passphrase: str, secret: str) -> str:
    """Derive user_id from user-provided passphrase."""
    normalized = passphrase.lower().strip()
    hash_input = f"passphrase:{normalized}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    return f"usr_{hash_bytes[:8].hex()}"

def get_current_session_id() -> str:
    """Get the session ID for the current request context."""
    # Implementation depends on how you're tracking sessions
    # Could use contextvars, request state, etc.
    from contextvars import ContextVar
    current_session: ContextVar[str] = ContextVar('current_session')
    return current_session.get()

async def require_auth() -> SessionState:
    """Require authentication for a tool call."""
    session_id = get_current_session_id()
    session = sessions.get(session_id)
    
    if not session or not session.is_authenticated:
        raise AuthenticationRequired(
            "Please connect your account first using connect_account() or connect_with_passphrase()."
        )
    
    return session
```

---

## Security Considerations

### Secrets Management

| Secret | Purpose | Storage |
|--------|---------|---------|
| `GOOGLE_CLIENT_SECRET` | OAuth token exchange | Secret Manager / env var |
| `IDENTITY_SECRET` | User ID derivation | Secret Manager / env var |
| User passphrases | Never stored | Derived to user_id only |

### OAuth Security

- [x] Use HTTPS for all endpoints
- [x] Validate `state` parameter to prevent CSRF
- [x] Store tokens securely (or don't store access tokens at all)
- [x] Use short-lived access tokens
- [x] Request minimum necessary scopes (`email`, `profile`)

### Passphrase Security

- [x] Never store raw passphrases
- [x] Use server-side secret in derivation
- [x] Normalize input (case-insensitive, trim whitespace)
- [x] Rate limit authentication attempts
- [ ] Consider adding pepper per-user (future)

### Session Security

- [x] Generate cryptographically random session IDs
- [x] Session timeout after inactivity
- [x] Clean up sessions on disconnect
- [ ] Consider signed session tokens (future)

### Data Access

- [x] All memory operations require authentication
- [x] User can only access their own memories (scope enforcement)
- [x] Server-side scope injection (client cannot override)

---

## Migration & Account Linking

### Linking Passphrase to Google Account

Users who started with passphrase can later link Google:

```python
@mcp.tool()
async def link_google_account() -> Dict[str, Any]:
    """
    Link your Google account to your existing memories.
    
    If you've been using a passphrase, this lets you also use Google sign-in
    while keeping all your existing memories.
    
    Returns:
        Link instructions or status
    """
    session_id = get_current_session_id()
    session = sessions.get(session_id)
    
    if not session or not session.is_authenticated:
        return {
            "status": "error",
            "message": "Please connect with your passphrase first, then link Google."
        }
    
    if session.auth_method == "oauth":
        return {
            "status": "already_linked",
            "message": "Your account is already linked to Google."
        }
    
    # Generate special linking URL that includes current user_id
    link_url = f"https://openreflect.run.app/oauth/link?session_id={session_id}&user_id={session.user_id}"
    
    return {
        "status": "link_available",
        "link_url": link_url,
        "message": "Click the link to add Google sign-in to your account. Your memories will be preserved."
    }
```

### User ID Collision Handling

In rare cases, different auth methods might theoretically produce the same user_id (hash collision). Mitigations:

1. **Different prefixes in hash input**: `google:` vs `passphrase:` ensures different derivation paths
2. **16 hex chars = 64 bits**: Collision probability is negligible at expected user scale
3. **Detection**: Log and alert if same user_id produced by different methods

---

## Environment Variables Summary

```bash
# Google OAuth (required for OAuth flow)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
OAUTH_REDIRECT_URI=https://openreflect.run.app/oauth/callback

# Identity derivation (required for both methods)
IDENTITY_SECRET=your-random-32-byte-secret-never-change-this

# Optional: Redis for session persistence
REDIS_URL=redis://10.0.0.1:6379

# Optional: Feature flags
ENABLE_PASSPHRASE_AUTH=true
REQUIRE_EMAIL_VERIFICATION=false
```

---

## Appendix A: UX Copy Suggestions

### First-Time User (ChatGPT)

```
AI: "I'd like to save this to your OpenReflect memory bank so I can remember 
     it across our conversations. Would you like to:
     
     1. **Sign in with Google** (recommended) - One click, works everywhere
     2. **Use a passphrase** - No Google account needed
     
     Which would you prefer?"
```

### Already Connected

```
AI: "Got it! I've saved that to your memory bank. You can access this memory
     from any AI assistant connected to OpenReflect."
```

### Cross-Client Reconnection

```
AI: "Welcome! I see you want to use OpenReflect. To access your existing 
     memories, please sign in with the same Google account or passphrase 
     you used before."
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-29 | Claude Opus 4.5 | Initial authentication design |

---

*This document should be reviewed and updated as the authentication system evolves.*
