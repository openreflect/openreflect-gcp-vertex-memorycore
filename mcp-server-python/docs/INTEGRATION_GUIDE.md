# OpenReflect Integration Guide

**Version**: 1.0  
**Date**: December 29, 2025  
**Authors**: Claude Opus 4.5 (AI Architect) in collaboration with OpenReflect Team  
**Status**: Implementation Reference  
**Related**: [AUTH_DESIGN.md](./AUTH_DESIGN.md), [TOOLS_GUIDE.md](./TOOLS_GUIDE.md), [ARCHITECTURE_STRATEGY.md](./ARCHITECTURE_STRATEGY.md)

---

## Table of Contents

1. [Overview](#overview)
2. [File Structure](#file-structure)
3. [New Files to Create](#new-files-to-create)
4. [Existing Files to Modify](#existing-files-to-modify)
5. [Session Context Propagation](#session-context-propagation)
6. [OAuth Router Integration](#oauth-router-integration)
7. [Google Cloud Console Setup](#google-cloud-console-setup)
8. [Environment Variables](#environment-variables)
9. [Deployment Checklist](#deployment-checklist)
10. [Implementation Order](#implementation-order)

---

## Overview

This guide provides step-by-step instructions for integrating authentication into the OpenReflect MCP server. It bridges the gap between the design documents (AUTH_DESIGN.md, ARCHITECTURE_STRATEGY.md) and the existing codebase.

### What This Guide Covers

1. **File structure** — What new files to create and where
2. **Session propagation** — How session_id flows from SSE connection to tools
3. **OAuth wiring** — How to add OAuth endpoints to FastAPI
4. **Google setup** — Cloud Console configuration for OAuth
5. **Deployment** — Cloud Run environment variables and checklist

### Prerequisites

Before starting, ensure you have:
- Access to Google Cloud Console
- The existing OpenReflect codebase
- Understanding of [AUTH_DESIGN.md](./AUTH_DESIGN.md) and [TOOLS_GUIDE.md](./TOOLS_GUIDE.md)

---

## File Structure

### Current Structure

```
mcp-server-python/
├── src/
│   ├── __init__.py
│   ├── app_state.py          # Global AppState singleton
│   ├── config.py             # Configuration from env vars
│   ├── formatters.py         # Response formatters
│   ├── prompts.py            # MCP prompts
│   ├── server_http.py        # FastAPI app, SSE handling
│   ├── server.py             # FastMCP server creation
│   ├── tools.py              # MCP tools
│   └── validators.py         # Input validators
├── deploy/
│   └── ...
├── docs/
│   └── ...
└── ...
```

### After Integration

```
mcp-server-python/
├── src/
│   ├── __init__.py
│   ├── app_state.py          # Global AppState singleton
│   ├── auth.py               # NEW: Authentication helpers
│   ├── config.py             # MODIFY: Add auth config
│   ├── formatters.py         # Response formatters
│   ├── oauth.py              # NEW: OAuth router
│   ├── prompts.py            # MCP prompts
│   ├── server_http.py        # MODIFY: Session propagation, OAuth router
│   ├── server.py             # FastMCP server creation
│   ├── sessions.py           # NEW: Session state management
│   ├── tools.py              # MODIFY: Add auth to tools
│   └── validators.py         # Input validators
├── deploy/
│   └── ...
├── docs/
│   └── ...
└── ...
```

---

## New Files to Create

### File 1: `src/sessions.py`

**Purpose**: Session state management, shared between server_http.py and tools.

```python
"""Session state management for MCP connections."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
import asyncio


@dataclass
class SessionState:
    """
    State for a single MCP session.
    
    Each SSE connection creates one SessionState.
    Authentication binds a user_id to the session.
    """
    session_id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    
    # Authentication state
    user_id: Optional[str] = None
    email: Optional[str] = None
    auth_method: Optional[str] = None  # "oauth" or "passphrase"
    authenticated_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if session has an authenticated user."""
        return self.user_id is not None
    
    def touch(self) -> None:
        """Update last_active timestamp."""
        self.last_active = datetime.utcnow()


# Global session store
# Key: session_id (str), Value: SessionState
sessions: Dict[str, SessionState] = {}


def get_session(session_id: str) -> Optional[SessionState]:
    """Get session by ID, returns None if not found."""
    return sessions.get(session_id)


def create_session(session_id: str) -> SessionState:
    """Create a new session."""
    session = SessionState(session_id=session_id)
    sessions[session_id] = session
    return session


def delete_session(session_id: str) -> None:
    """Remove a session."""
    sessions.pop(session_id, None)


async def bind_session_to_user(
    session_id: str,
    user_id: str,
    email: Optional[str] = None,
    auth_method: str = "oauth",
) -> bool:
    """
    Bind an authenticated user to a session.
    
    Called after successful OAuth callback or passphrase validation.
    
    Args:
        session_id: The MCP session ID
        user_id: The derived user_id (from OAuth sub or passphrase hash)
        email: User's email (from OAuth, None for passphrase)
        auth_method: "oauth" or "passphrase"
    
    Returns:
        True if session was found and bound, False if session not found
    """
    session = sessions.get(session_id)
    if not session:
        return False
    
    session.user_id = user_id
    session.email = email
    session.auth_method = auth_method
    session.authenticated_at = datetime.utcnow()
    session.touch()
    
    return True


def unbind_session(session_id: str) -> bool:
    """
    Remove authentication from a session (logout).
    
    Returns:
        True if session was found, False otherwise
    """
    session = sessions.get(session_id)
    if not session:
        return False
    
    session.user_id = None
    session.email = None
    session.auth_method = None
    session.authenticated_at = None
    session.touch()
    
    return True
```

---

### File 2: `src/auth.py`

**Purpose**: Authentication helpers, identity derivation, context management.

```python
"""Authentication helpers for OpenReflect MCP."""

import hashlib
import hmac
import logging
import os
import time
from contextvars import ContextVar
from typing import Optional

from .sessions import SessionState, get_session

logger = logging.getLogger(__name__)

# Context variable for current session ID
# Set by server_http.py before calling tools
_current_session_id: ContextVar[Optional[str]] = ContextVar(
    'current_session_id', 
    default=None
)


class AuthenticationRequired(Exception):
    """Raised when a tool requires authentication but session is not authenticated."""
    pass


# ============================================================================
# Context Management
# ============================================================================

def set_current_session_id(session_id: str) -> None:
    """
    Set the current session ID in context.
    
    Called by server_http.py before routing to tools.
    """
    _current_session_id.set(session_id)


def get_current_session_id() -> Optional[str]:
    """Get the current session ID from context."""
    return _current_session_id.get()


def get_current_session() -> Optional[SessionState]:
    """Get the current session from context."""
    session_id = get_current_session_id()
    if not session_id:
        return None
    return get_session(session_id)


# ============================================================================
# Authentication Checks
# ============================================================================

async def require_auth() -> SessionState:
    """
    Require authentication for the current request.
    
    Returns:
        The authenticated SessionState
    
    Raises:
        AuthenticationRequired: If not authenticated
    
    Usage in tools:
        try:
            session = await require_auth()
        except AuthenticationRequired as e:
            return format_error_response(str(e))
    """
    session = get_current_session()
    
    if not session:
        raise AuthenticationRequired(
            "No active session. Please reconnect to OpenReflect."
        )
    
    if not session.is_authenticated:
        raise AuthenticationRequired(
            "Please connect your account first using connect_account() "
            "or connect_with_passphrase()."
        )
    
    session.touch()
    return session


def get_session_if_authenticated() -> Optional[SessionState]:
    """
    Get session if authenticated, None otherwise.
    
    Use for optional auth scenarios.
    """
    session = get_current_session()
    if session and session.is_authenticated:
        session.touch()
        return session
    return None


# ============================================================================
# Identity Derivation
# ============================================================================

def _get_identity_secret() -> str:
    """
    Get the identity derivation secret from environment.
    
    This secret is combined with user identifiers to derive user_id.
    MUST be kept secret and NEVER changed after deployment.
    """
    secret = os.environ.get("IDENTITY_SECRET")
    if not secret:
        raise ValueError(
            "IDENTITY_SECRET environment variable is required. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return secret


def derive_user_id_from_google(google_sub: str) -> str:
    """
    Derive a deterministic user_id from Google's sub claim.
    
    Google's 'sub' is a stable, unique identifier for the Google account.
    Same Google account → same sub → same user_id (always).
    
    Args:
        google_sub: The 'sub' claim from Google's ID token
    
    Returns:
        Deterministic user_id: "usr_" + 16 hex chars
    """
    secret = _get_identity_secret()
    hash_input = f"google:{google_sub}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    return f"usr_{hash_bytes[:8].hex()}"


def derive_user_id_from_passphrase(passphrase: str) -> str:
    """
    Derive a deterministic user_id from a passphrase.
    
    Same passphrase → same user_id (always).
    
    Args:
        passphrase: User-provided passphrase
    
    Returns:
        Deterministic user_id: "usr_" + 16 hex chars
    """
    secret = _get_identity_secret()
    
    # Normalize: lowercase, strip whitespace
    normalized = passphrase.lower().strip()
    
    hash_input = f"passphrase:{normalized}:{secret}"
    hash_bytes = hashlib.sha256(hash_input.encode()).digest()
    return f"usr_{hash_bytes[:8].hex()}"


# ============================================================================
# Session Token (CSRF Protection for OAuth)
# ============================================================================

def generate_session_token(session_id: str, expires_in: int = 600) -> str:
    """
    Generate a signed session token for OAuth state parameter.
    
    This prevents CSRF attacks during the OAuth flow.
    
    Args:
        session_id: The MCP session ID to bind
        expires_in: Token validity in seconds (default: 10 minutes)
    
    Returns:
        Signed token: "session_id:expiry:signature"
    """
    secret = _get_identity_secret()
    expiry = int(time.time()) + expires_in
    
    payload = f"{session_id}:{expiry}"
    signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> Optional[str]:
    """
    Verify a session token and extract the session_id.
    
    Args:
        token: The token from OAuth state parameter
    
    Returns:
        session_id if valid and not expired, None otherwise
    """
    try:
        secret = _get_identity_secret()
        parts = token.split(":")
        if len(parts) != 3:
            return None
        
        session_id, expiry_str, signature = parts
        expiry = int(expiry_str)
        
        # Check expiry
        if time.time() > expiry:
            logger.warning(f"Session token expired for session {session_id}")
            return None
        
        # Verify signature
        payload = f"{session_id}:{expiry_str}"
        expected_signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning(f"Invalid session token signature")
            return None
        
        return session_id
        
    except Exception as e:
        logger.warning(f"Failed to verify session token: {e}")
        return None
```

---

### File 3: `src/oauth.py`

**Purpose**: OAuth 2.0 router for Google authentication.

```python
"""OAuth 2.0 router for Google authentication."""

import logging
import os
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx

from .auth import (
    derive_user_id_from_google,
    generate_session_token,
    verify_session_token,
)
from .sessions import bind_session_to_user, get_session

logger = logging.getLogger(__name__)

# Create router
oauth_router = APIRouter(prefix="/oauth", tags=["oauth"])

# ============================================================================
# Configuration
# ============================================================================

def _get_oauth_config():
    """Get OAuth configuration from environment."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.environ.get(
        "OAUTH_REDIRECT_URI",
        "https://openreflect.run.app/oauth/callback"
    )
    
    if not client_id or not client_secret:
        raise ValueError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables are required"
        )
    
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


# ============================================================================
# OAuth Endpoints
# ============================================================================

@oauth_router.get("/authorize")
async def authorize(session_id: str):
    """
    Initiate OAuth flow.
    
    Redirects user to Google's authorization server.
    
    Args:
        session_id: The MCP session ID to bind after successful auth
    
    Returns:
        HTTP 302 redirect to Google OAuth
    """
    if not session_id:
        raise HTTPException(400, "session_id is required")
    
    # Verify session exists
    session = get_session(session_id)
    if not session:
        raise HTTPException(400, "Invalid session_id")
    
    try:
        config = _get_oauth_config()
    except ValueError as e:
        logger.error(f"OAuth not configured: {e}")
        raise HTTPException(500, "OAuth not configured")
    
    # Generate signed state token (CSRF protection)
    state = generate_session_token(session_id)
    
    # Build Google OAuth URL
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": "email profile openid",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",  # Always show account chooser
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    logger.info(f"Initiating OAuth for session {session_id}")
    return RedirectResponse(auth_url)


@oauth_router.get("/callback")
async def callback(code: str, state: str):
    """
    Handle OAuth callback from Google.
    
    Exchanges authorization code for tokens, extracts user info,
    and binds the session to the authenticated user.
    
    Args:
        code: Authorization code from Google
        state: Signed state token containing session_id
    
    Returns:
        HTML success page (auto-closes popup)
    """
    # Verify state token and extract session_id
    session_id = verify_session_token(state)
    if not session_id:
        logger.warning("Invalid or expired OAuth state token")
        return HTMLResponse(
            _error_page("Authentication Failed", "Invalid or expired session. Please try again."),
            status_code=400
        )
    
    # Verify session still exists
    session = get_session(session_id)
    if not session:
        logger.warning(f"Session {session_id} no longer exists")
        return HTMLResponse(
            _error_page("Session Expired", "Your session has expired. Please reconnect to OpenReflect."),
            status_code=400
        )
    
    try:
        config = _get_oauth_config()
    except ValueError as e:
        logger.error(f"OAuth not configured: {e}")
        return HTMLResponse(
            _error_page("Configuration Error", "OAuth is not properly configured."),
            status_code=500
        )
    
    # Exchange authorization code for tokens
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "redirect_uri": config["redirect_uri"],
                    "grant_type": "authorization_code",
                }
            )
            
            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                return HTMLResponse(
                    _error_page("Authentication Failed", "Could not complete sign-in. Please try again."),
                    status_code=500
                )
            
            tokens = token_response.json()
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        return HTMLResponse(
            _error_page("Connection Error", "Could not connect to Google. Please try again."),
            status_code=500
        )
    
    # Get user info from Google
    try:
        async with httpx.AsyncClient() as client:
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            
            if userinfo_response.status_code != 200:
                logger.error(f"User info request failed: {userinfo_response.text}")
                return HTMLResponse(
                    _error_page("Authentication Failed", "Could not retrieve your information."),
                    status_code=500
                )
            
            user_info = userinfo_response.json()
    except Exception as e:
        logger.error(f"User info error: {e}")
        return HTMLResponse(
            _error_page("Connection Error", "Could not retrieve your information."),
            status_code=500
        )
    
    # Extract user identity
    google_sub = user_info.get("id")
    email = user_info.get("email")
    
    if not google_sub:
        logger.error("No 'id' in user info response")
        return HTMLResponse(
            _error_page("Authentication Failed", "Could not verify your identity."),
            status_code=500
        )
    
    # Derive stable user_id
    user_id = derive_user_id_from_google(google_sub)
    
    # Bind session to user
    success = await bind_session_to_user(
        session_id=session_id,
        user_id=user_id,
        email=email,
        auth_method="oauth"
    )
    
    if not success:
        logger.error(f"Failed to bind session {session_id} to user {user_id}")
        return HTMLResponse(
            _error_page("Session Error", "Could not complete authentication. Please try again."),
            status_code=500
        )
    
    logger.info(f"Successfully authenticated session {session_id} as user {user_id} ({email})")
    
    return HTMLResponse(_success_page(email))


# ============================================================================
# HTML Pages
# ============================================================================

def _success_page(email: Optional[str]) -> str:
    """Generate success page HTML."""
    display_email = email or "User"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OpenReflect - Connected!</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
                             'Helvetica Neue', Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #2d1b4e 100%);
                color: #ffffff;
            }}
            .container {{
                text-align: center;
                padding: 3rem 2rem;
                max-width: 400px;
            }}
            .checkmark {{
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #00d9ff 0%, #00ff88 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 1.5rem;
                font-size: 2.5rem;
                animation: pulse 2s ease-in-out infinite;
            }}
            @keyframes pulse {{
                0%, 100% {{ transform: scale(1); }}
                50% {{ transform: scale(1.05); }}
            }}
            h1 {{
                font-size: 1.75rem;
                font-weight: 600;
                margin: 0 0 0.75rem;
                background: linear-gradient(135deg, #00d9ff 0%, #00ff88 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            .email {{
                color: #a0a0c0;
                font-size: 0.95rem;
                margin-bottom: 1.5rem;
            }}
            .message {{
                color: #808090;
                font-size: 0.9rem;
                line-height: 1.5;
            }}
            .countdown {{
                color: #606070;
                font-size: 0.8rem;
                margin-top: 1.5rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="checkmark">✓</div>
            <h1>Connected to OpenReflect!</h1>
            <p class="email">Signed in as {display_email}</p>
            <p class="message">
                Your memory bank is now connected. You can close this window 
                and return to your AI assistant.
            </p>
            <p class="countdown" id="countdown">This window will close in 5 seconds...</p>
        </div>
        <script>
            let seconds = 5;
            const countdownEl = document.getElementById('countdown');
            const interval = setInterval(() => {{
                seconds--;
                if (seconds <= 0) {{
                    clearInterval(interval);
                    countdownEl.textContent = 'Closing...';
                    window.close();
                }} else {{
                    countdownEl.textContent = `This window will close in ${{seconds}} seconds...`;
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    """


def _error_page(title: str, message: str) -> str:
    """Generate error page HTML."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OpenReflect - Error</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
                             'Helvetica Neue', Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #1a0a0a 0%, #2d1a1a 50%, #3d2020 100%);
                color: #ffffff;
            }}
            .container {{
                text-align: center;
                padding: 3rem 2rem;
                max-width: 400px;
            }}
            .error-icon {{
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #ff4444 0%, #ff6b6b 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 1.5rem;
                font-size: 2.5rem;
            }}
            h1 {{
                font-size: 1.75rem;
                font-weight: 600;
                margin: 0 0 0.75rem;
                color: #ff6b6b;
            }}
            .message {{
                color: #c0a0a0;
                font-size: 0.95rem;
                line-height: 1.5;
                margin-bottom: 1.5rem;
            }}
            .close-btn {{
                background: linear-gradient(135deg, #ff4444 0%, #ff6b6b 100%);
                color: white;
                border: none;
                padding: 0.75rem 2rem;
                font-size: 1rem;
                border-radius: 8px;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .close-btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(255, 68, 68, 0.4);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">✕</div>
            <h1>{title}</h1>
            <p class="message">{message}</p>
            <button class="close-btn" onclick="window.close()">Close Window</button>
        </div>
    </body>
    </html>
    """
```

---

## Existing Files to Modify

### Modification 1: `src/config.py`

**Add** authentication-related configuration fields:

```python
# Add to existing Config class

@dataclass
class Config:
    # ... existing fields ...
    
    # Authentication config (NEW)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    oauth_redirect_uri: Optional[str] = None
    identity_secret: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            # ... existing fields ...
            
            # Authentication config (NEW)
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            oauth_redirect_uri=os.getenv(
                "OAUTH_REDIRECT_URI", 
                "https://openreflect.run.app/oauth/callback"
            ),
            identity_secret=os.getenv("IDENTITY_SECRET"),
        )
    
    def is_auth_configured(self) -> bool:
        """Check if authentication is properly configured."""
        return bool(
            self.google_client_id and 
            self.google_client_secret and 
            self.identity_secret
        )
```

---

### Modification 2: `src/server_http.py`

**Changes needed**:

1. Import new modules
2. Replace `_sse_sessions` with `sessions` from sessions.py
3. Add session context before tool calls
4. Include OAuth router

**Full modified file** (showing key changes):

```python
"""HTTP server module for Cloud Run deployment using SSE transport."""

import asyncio
from dataclasses import asdict, is_dataclass
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse
import mcp.types as types

# Import the server creation factory directly
from .server import create_server
from .app_state import app as app_state

# NEW IMPORTS
from .sessions import SessionState, sessions, create_session, delete_session, get_session
from .auth import set_current_session_id
from .oauth import oauth_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize the MCP server instance globally
mcp_server = create_server()

# REMOVED: _sse_sessions dict (now using sessions from sessions.py)
# _sse_sessions: Dict[str, "asyncio.Queue[Dict[str, Any]]"] = {}  # OLD


# ... (keep _to_jsonable function unchanged) ...


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... (keep unchanged) ...


# Create FastAPI app
fastapi_app = FastAPI(title="OpenReflect MCP Server", lifespan=lifespan)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NEW: Include OAuth router
fastapi_app.include_router(oauth_router)


# ... (keep _authorize function and health/root endpoints unchanged) ...


async def handle_sse_connection(
    request: Request,
    initial_request: Optional[Dict[str, Any]] = None,
):
    """Shared handler for SSE connection."""
    
    # ... (keep _first_forwarded_value and _get_external_base_url unchanged) ...
    
    async def event_stream(
        initial_request: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        session_id = None  # Initialize for finally block
        try:
            # Simple unique session ID
            session_id = str(uuid.uuid4())
            logger.info(f"New SSE session: {session_id}")

            # NEW: Use SessionState instead of bare queue
            session = create_session(session_id)

            # Construct the absolute URL for the /message endpoint
            base_url = _get_external_base_url(request)
            message_endpoint = f"{base_url}/message?session_id={session_id}"
            
            # The MCP spec says the first event is the endpoint URL
            yield f"event: endpoint\ndata: {message_endpoint}\n\n"

            # If the client POSTed an initial JSON-RPC message to /sse
            if initial_request:
                # NEW: Set session context before handling
                set_current_session_id(session_id)
                if (initial_resp := await _handle_jsonrpc(initial_request)) is not None:
                    await session.queue.put(initial_resp)

            # Stream queued JSON-RPC responses over SSE, with keepalives.
            while True:
                try:
                    # NEW: Use session.queue instead of bare queue
                    msg = await asyncio.wait_for(session.queue.get(), timeout=15)
                    payload = json.dumps(
                        _to_jsonable(msg),
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                    yield f"event: message\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                
        except asyncio.CancelledError:
            logger.info(f"SSE session disconnected: {session_id}")
        finally:
            if session_id:
                # NEW: Use delete_session instead of dict pop
                delete_session(session_id)

    return StreamingResponse(
        event_stream(initial_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@fastapi_app.post("/message")
async def message_endpoint(request: Request, session_id: str = None):
    """Handle JSON-RPC messages from the client."""
    if (resp := _authorize(request)) is not None:
        return resp

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        # NEW: Set session context before handling
        if session_id:
            set_current_session_id(session_id)
        
        resp = await _handle_jsonrpc(body)

        # If this request is associated with an active SSE session
        if session_id:
            # NEW: Use get_session instead of dict lookup
            session = get_session(session_id)
            if session:
                if resp is not None:
                    await session.queue.put(resp)
                return Response(status_code=202)

        # Fallback: no SSE session found
        if resp is None:
            return Response(status_code=200)
        return resp

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": body.get("id") if isinstance(body, dict) else None,
            "error": {"code": -32603, "message": str(e)},
        }


# For Cloud Run, use the FastAPI app directly
app = fastapi_app
```

---

### Modification 3: `src/tools.py`

**Add** authentication tools and modify existing tools.

See [TOOLS_GUIDE.md](./TOOLS_GUIDE.md) for complete migration guide for each tool.

**Key additions at the top of the file**:

```python
# Add to imports at top of tools.py (after existing imports)

from .auth import (
    require_auth,
    AuthenticationRequired,
    get_current_session,
    get_current_session_id,  # Used by auth tools
    derive_user_id_from_passphrase,
)
from .sessions import bind_session_to_user, unbind_session, get_session
```

**Complete imports section for reference** (showing existing + new):

```python
"""MCP Tools"""

import logging
import os  # NEW: for SERVICE_URL env var
from typing import Any, Dict, List, Optional

import vertexai
from mcp.server.fastmcp import FastMCP

from .app_state import app
from .formatters import (
    format_conversation_events,
    format_error_response,
    format_memory,
    format_success_response,
    format_ttl_expiration,
)
from .validators import validate_conversation, validate_memory_fact, validate_scope

# NEW: Authentication imports
from .auth import (
    require_auth,
    AuthenticationRequired,
    get_current_session,
    get_current_session_id,
    derive_user_id_from_passphrase,
)
from .sessions import bind_session_to_user, unbind_session, get_session

logger = logging.getLogger(__name__)
```

**Add new authentication tools** inside `register_tools()`:

```python
# ========================================================================
# Authentication Tools (NEW SECTION)
# ========================================================================

@mcp.tool()
async def connect_account() -> Dict[str, Any]:
    """
    Connect your Google account to access your memories across all AI assistants.
    
    Returns:
        Connection status and OAuth URL if needed
    """
    from .auth import get_current_session_id
    
    session_id = get_current_session_id()
    if not session_id:
        return format_error_response("No active session")
    
    session = get_session(session_id)
    if session and session.is_authenticated:
        return format_success_response({
            "status": "already_connected",
            "email": session.email,
            "auth_method": session.auth_method,
            "message": "Your account is already connected!"
        })
    
    # Generate auth URL
    # Use environment variable for base URL, fallback to default
    import os
    base_url = os.environ.get("SERVICE_URL", "https://openreflect.run.app")
    auth_url = f"{base_url}/oauth/authorize?session_id={session_id}"
    
    return format_success_response({
        "status": "auth_required",
        "auth_url": auth_url,
        "message": "Please click the link to sign in with Google and connect your memory bank."
    })

@mcp.tool()
async def connect_with_passphrase(passphrase: str) -> Dict[str, Any]:
    """
    Connect using a passphrase instead of Google sign-in.
    
    Use the same passphrase across all AI assistants to access the same memories.
    
    Args:
        passphrase: A memorable phrase (case-insensitive)
    
    Returns:
        Connection status
    """
    from .auth import get_current_session_id
    
    session_id = get_current_session_id()
    if not session_id:
        return format_error_response("No active session")
    
    # Validate passphrase
    if not passphrase or len(passphrase.strip()) < 4:
        return format_error_response(
            "Please provide a passphrase with at least 4 characters."
        )
    
    # Derive user_id from passphrase
    user_id = derive_user_id_from_passphrase(passphrase)
    
    # Bind session to user
    success = await bind_session_to_user(
        session_id=session_id,
        user_id=user_id,
        email=None,
        auth_method="passphrase"
    )
    
    if not success:
        return format_error_response("Could not connect. Please try again.")
    
    return format_success_response({
        "status": "connected",
        "message": "Connected to your memory bank!",
        "tip": "Use this same passphrase in other AI assistants to access your memories.",
        "upgrade_hint": "For easier access, you can link your Google account with connect_account()."
    })

@mcp.tool()
async def check_connection() -> Dict[str, Any]:
    """
    Check your current connection status.
    
    Returns:
        Current authentication status
    """
    session = get_current_session()
    
    if not session or not session.is_authenticated:
        return format_success_response({
            "status": "not_connected",
            "message": "You're not connected. Use connect_account() or connect_with_passphrase() to connect."
        })
    
    return format_success_response({
        "status": "connected",
        "user_id": session.user_id,
        "email": session.email,
        "auth_method": session.auth_method,
        "connected_since": session.authenticated_at.isoformat() if session.authenticated_at else None
    })

@mcp.tool()
async def disconnect() -> Dict[str, Any]:
    """
    Disconnect from your memory bank for this session.
    
    Returns:
        Disconnection confirmation
    """
    from .auth import get_current_session_id
    
    session_id = get_current_session_id()
    if session_id:
        unbind_session(session_id)
    
    return format_success_response({
        "status": "disconnected",
        "message": "Disconnected from your memory bank. Your memories are safe and you can reconnect anytime."
    })
```

---

## Session Context Propagation

### How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SESSION CONTEXT FLOW                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. SSE Connection Established                                          │
│     └── server_http.py: session_id = uuid4()                            │
│     └── server_http.py: create_session(session_id)                      │
│                                                                         │
│  2. JSON-RPC Request Arrives (/message?session_id=xxx)                  │
│     └── server_http.py: set_current_session_id(session_id)              │
│                                                                         │
│  3. Tool is Called                                                      │
│     └── tools.py: session = await require_auth()                        │
│     └── auth.py: session_id = get_current_session_id()                  │
│     └── auth.py: session = get_session(session_id)                      │
│     └── auth.py: returns session if authenticated                       │
│                                                                         │
│  4. Tool Uses Authenticated User ID                                     │
│     └── tools.py: scope = {"user_id": session.user_id}                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `create_session(session_id)` | sessions.py | Create SessionState on SSE connect |
| `delete_session(session_id)` | sessions.py | Clean up on SSE disconnect |
| `set_current_session_id(session_id)` | auth.py | Set context before tool call |
| `get_current_session_id()` | auth.py | Get context in tool |
| `require_auth()` | auth.py | Verify authenticated, return session |

### Context Variables

Python's `contextvars` module provides async-safe context that works across `await` boundaries:

```python
from contextvars import ContextVar

_current_session_id: ContextVar[Optional[str]] = ContextVar(
    'current_session_id', 
    default=None
)
```

This ensures that even with concurrent requests, each request sees its own session_id.

---

## OAuth Router Integration

### Step 1: Create OAuth Router

The `oauth_router` is defined in `src/oauth.py` (see [New Files to Create](#new-files-to-create)).

### Step 2: Include in FastAPI App

In `src/server_http.py`:

```python
from .oauth import oauth_router

# After creating fastapi_app:
fastapi_app.include_router(oauth_router)
```

### Step 3: Verify Endpoints

After integration, these endpoints are available:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/oauth/authorize` | GET | Initiate OAuth flow |
| `/oauth/callback` | GET | Handle Google callback |

### Full OAuth Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         OAUTH FLOW                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. User calls connect_account() tool                                   │
│     └── Returns: auth_url = "https://openreflect.run.app/oauth/         │
│                              authorize?session_id=sess_123"             │
│                                                                         │
│  2. AI presents link to user                                            │
│     └── ChatGPT shows clickable link in chat                            │
│                                                                         │
│  3. User clicks link                                                    │
│     └── Browser opens /oauth/authorize?session_id=sess_123              │
│                                                                         │
│  4. Server redirects to Google                                          │
│     └── /oauth/authorize generates signed state token                   │
│     └── Redirects to accounts.google.com/o/oauth2/v2/auth               │
│                                                                         │
│  5. User signs in with Google                                           │
│     └── Google shows consent screen                                     │
│     └── User clicks "Allow"                                             │
│                                                                         │
│  6. Google redirects back to callback                                   │
│     └── GET /oauth/callback?code=xxx&state=yyy                          │
│                                                                         │
│  7. Server processes callback                                           │
│     └── Verifies state token → extracts session_id                      │
│     └── Exchanges code for tokens                                       │
│     └── Gets user info (sub, email)                                     │
│     └── Derives user_id from google_sub                                 │
│     └── Binds session to user                                           │
│                                                                         │
│  8. User sees success page                                              │
│     └── "Connected to OpenReflect!"                                     │
│     └── Auto-closes after 5 seconds                                     │
│                                                                         │
│  9. User returns to chat                                                │
│     └── Next tool call is authenticated                                 │
│     └── scope = {"user_id": "usr_abc123"}                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Google Cloud Console Setup

### Step 1: Navigate to Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (e.g., `directed-asset-479716-f6`)
3. Navigate to **APIs & Services** → **Credentials**

### Step 2: Create OAuth Client ID

1. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
2. Select **Web application**
3. Name: `OpenReflect MCP`
4. **Authorized redirect URIs**: Add your Cloud Run callback URL
   - Example: `https://openreflect-mcp-abcdef-uc.a.run.app/oauth/callback`
   - Or your custom domain: `https://openreflect.run.app/oauth/callback`
5. Click **CREATE**
6. **Copy** the Client ID and Client Secret

### Step 3: Configure OAuth Consent Screen

1. Navigate to **APIs & Services** → **OAuth consent screen**
2. Select **External** (or **Internal** if G Suite org)
3. Fill in:
   - **App name**: `OpenReflect`
   - **User support email**: Your email
   - **Developer contact email**: Your email
4. **Scopes**: Add:
   - `email`
   - `profile`
   - `openid`
5. **Test users**: Add your email for testing (if External)
6. Click **Save and Continue**

### Step 4: Note Your Credentials

You need:
- **Client ID**: `xxxxx.apps.googleusercontent.com`
- **Client Secret**: `GOCSPX-xxxxx`

These go into your Cloud Run environment variables.

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | `directed-asset-479716-f6` |
| `GOOGLE_CLOUD_LOCATION` | GCP region | `us-central1` |
| `AGENT_ENGINE_NAME` | Pre-created engine | `projects/.../reasoningEngines/123` |
| `GOOGLE_CLIENT_ID` | OAuth client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | `GOCSPX-xxx` |
| `IDENTITY_SECRET` | User ID derivation secret | `<random 64 hex chars>` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OAUTH_REDIRECT_URI` | OAuth callback URL | `https://openreflect.run.app/oauth/callback` |
| `SERVICE_URL` | Base URL for the service | `https://openreflect.run.app` |
| `CONNECTOR_BEARER_TOKEN` | Optional API auth | None (open) |

### Generate IDENTITY_SECRET

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**CRITICAL**: This secret MUST:
- Be kept secret
- Never be changed after deployment (changing it invalidates all user_ids)
- Be backed up securely

### Set Environment Variables in Cloud Run

```bash
gcloud run services update openreflect-mcp \
  --region us-central1 \
  --set-env-vars \
    GOOGLE_CLOUD_PROJECT=directed-asset-479716-f6,\
    GOOGLE_CLOUD_LOCATION=us-central1,\
    AGENT_ENGINE_NAME=projects/directed-asset-479716-f6/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID,\
    GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com,\
    GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET,\
    IDENTITY_SECRET=YOUR_64_CHAR_HEX_SECRET,\
    OAUTH_REDIRECT_URI=https://YOUR_CLOUD_RUN_URL/oauth/callback,\
    SERVICE_URL=https://YOUR_CLOUD_RUN_URL
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Generate `IDENTITY_SECRET` and store securely
- [ ] Create OAuth credentials in Google Cloud Console
- [ ] Configure OAuth consent screen
- [ ] Create Agent Engine (if not existing)
- [ ] Note the Agent Engine resource name

### Code Changes

- [ ] Create `src/sessions.py`
- [ ] Create `src/auth.py`
- [ ] Create `src/oauth.py`
- [ ] Modify `src/config.py`
- [ ] Modify `src/server_http.py`
- [ ] Modify `src/tools.py` (add auth tools)
- [ ] Migrate existing tools to require auth (see TOOLS_GUIDE.md)

### Environment Configuration

- [ ] Set `GOOGLE_CLOUD_PROJECT`
- [ ] Set `GOOGLE_CLOUD_LOCATION`
- [ ] Set `AGENT_ENGINE_NAME`
- [ ] Set `GOOGLE_CLIENT_ID`
- [ ] Set `GOOGLE_CLIENT_SECRET`
- [ ] Set `IDENTITY_SECRET`
- [ ] Set `OAUTH_REDIRECT_URI` (must match Cloud Console)
- [ ] Set `SERVICE_URL`

### Verification

- [ ] Deploy to Cloud Run
- [ ] Verify `/health` endpoint returns `healthy`
- [ ] Test `connect_account()` returns valid auth URL
- [ ] Complete OAuth flow in browser
- [ ] Verify session is authenticated after OAuth
- [ ] Test `create_memory()` with authenticated session
- [ ] Verify scope is server-enforced (user_id from session)
- [ ] Test cross-client: authenticate in ChatGPT, verify same memories in Claude

---

## Implementation Order

Recommended order for implementing changes:

### Phase 1: Foundation (No Breaking Changes)

1. Create `src/sessions.py`
2. Create `src/auth.py`
3. Create `src/oauth.py`

These files can be added without breaking existing functionality.

### Phase 2: Integration

4. Modify `src/config.py` (add auth config fields)
5. Modify `src/server_http.py`:
   - Add imports
   - Replace `_sse_sessions` with `sessions`
   - Add `set_current_session_id()` calls
   - Include OAuth router

### Phase 3: Auth Tools

6. Add authentication tools to `src/tools.py`:
   - `connect_account`
   - `connect_with_passphrase`
   - `check_connection`
   - `disconnect`

### Phase 4: Tool Migration

7. Migrate existing tools one by one:
   - `create_memory`
   - `retrieve_memories`
   - `generate_memories`
   - `list_memories`
   - `search_memories`
   - `fetch_memory`
   - `delete_memory`

### Phase 5: Deployment

8. Set environment variables
9. Deploy to Cloud Run
10. Verify OAuth redirect URI matches
11. Test end-to-end

---

## Troubleshooting

### OAuth "redirect_uri_mismatch" Error

**Cause**: The redirect URI in your code doesn't match what's configured in Google Cloud Console.

**Fix**:
1. Check `OAUTH_REDIRECT_URI` env var
2. Ensure it exactly matches the URI in Cloud Console
3. Include protocol (`https://`) and path (`/oauth/callback`)

### "IDENTITY_SECRET environment variable is required"

**Cause**: Missing `IDENTITY_SECRET` environment variable.

**Fix**:
```bash
# Generate secret
python -c "import secrets; print(secrets.token_hex(32))"

# Set in Cloud Run
gcloud run services update openreflect-mcp --set-env-vars IDENTITY_SECRET=<your-secret>
```

### "No active session" Error

**Cause**: Session context not being propagated to tools.

**Fix**:
1. Verify `set_current_session_id()` is called before `_handle_jsonrpc()`
2. Verify session exists in `sessions` dict
3. Check logs for session creation/deletion

### OAuth Popup Doesn't Close

**Cause**: Browser blocking window.close() for security.

**Status**: Expected behavior in some browsers. User can manually close.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-29 | Claude Opus 4.5 | Initial comprehensive integration guide |

---

*This document should be updated as the integration evolves and new patterns emerge.*
