"""HTTP server module for Cloud Run deployment using SSE transport."""

import asyncio
from dataclasses import asdict, is_dataclass
import json
import logging
import os
import sys
import uuid
import base64
import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlencode, parse_qs

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse
import mcp.types as types

# Import the server creation factory directly
from .server import create_server
from .app_state import (
    app as app_state,
    SessionState,
    current_session_id,
    current_user_id,
    current_user_email,
    current_user_scopes,
)
from .auth import derive_user_id_from_google

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize the MCP server instance globally
mcp_server = create_server()

# Active SSE sessions: session_id -> outbound JSON-RPC message queue
_sse_sessions: Dict[str, "asyncio.Queue[Dict[str, Any]]"] = {}


def _to_jsonable(obj: Any) -> Any:
    """
    Convert arbitrary objects into JSON-serializable structures.

    This is critical for SSE `event: message` payloads: some FastMCP versions
    can yield Tool/Prompt objects that must be converted via `model_dump()`.
    """
    # FastAPI's encoder already handles many common types (Pydantic, dataclasses, etc.)
    try:
        return jsonable_encoder(obj)
    except Exception:
        pass

    # Fallback: handle a few shapes explicitly.
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        try:
            return _to_jsonable(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return _to_jsonable(obj.dict())
        except Exception:
            pass
    if is_dataclass(obj):
        try:
            return _to_jsonable(asdict(obj))
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return _to_jsonable(vars(obj))
        except Exception:
            pass
    return str(obj)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage FastAPI and FastMCP lifecycles."""
    # Start FastMCP lifespan (which initializes app_state and Vertex AI client)
    # We access the internal context manager if available, or manually trigger the user-defined lifespan
    # FastMCP exposes 'lifespan_context' in recent versions.
    # If not, we might need to manually call the function passed to FastMCP.
    
    # Check if we can enter the lifespan context
    if hasattr(mcp_server, 'lifespan_context'):
        async with mcp_server.lifespan_context:
            logger.info("MCP Server lifespan started (In-Process)")
            yield
    else:
        # Fallback: Manually trigger the lifespan function defined in server.py
        # defined as: async def lifespan(server: FastMCP): ...
        # server.py defines it and passes it to FastMCP constructor.
        # We can try to access it via mcp_server._lifespan (if stored) or just run it if we knew it.
        # But we imported create_server, not the lifespan function directly (though we could).
        
        # Let's try to rely on the side effects.
        # If FastMCP doesn't expose a context, we might skip strict lifespan management 
        # but we need 'app_state.config' to be loaded.
        # Let's import the lifespan function from server.py to be safe.
        from .server import lifespan as user_lifespan
        async with user_lifespan(mcp_server):
            logger.info("MCP Server lifespan started (Manual)")
            yield

# Create FastAPI app
fastapi_app = FastAPI(title="OpenReflect MCP Server", lifespan=lifespan)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional bearer token for connector-facing auth
CONNECTOR_BEARER_TOKEN = os.getenv("CONNECTOR_BEARER_TOKEN")

def _authorize(request: Request) -> Optional[Response]:
    """Optional bearer token auth for connector-facing endpoints."""
    # If no token configured, allow access (MVP/dev open mode).
    if not CONNECTOR_BEARER_TOKEN:
        return None

    # Token is configured — enforce bearer auth.
    auth_header = request.headers.get("authorization")
    expected = f"Bearer {CONNECTOR_BEARER_TOKEN}"
    if auth_header != expected:
        logger.warning("Unauthorized request: missing/invalid bearer token")
        return Response(
            content=json.dumps({"error": "Unauthorized"}),
            status_code=401,
            media_type="application/json",
        )
    return None


def _first_forwarded_value(value: Optional[str]) -> Optional[str]:
    """Return the first comma-separated value from a forwarded header."""
    if not value:
        return None
    return value.split(",")[0].strip()


def _get_external_base_url(request: Request) -> str:
    """Construct an externally-reachable base URL (scheme + host)."""
    proto = _first_forwarded_value(request.headers.get("x-forwarded-proto"))
    host = (
        _first_forwarded_value(request.headers.get("x-forwarded-host"))
        or request.headers.get("host")
    )
    if proto and host:
        return f"{proto}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _normalize_resource_uri(uri: str) -> str:
    """Normalize resource URIs for aud/resource comparisons (strip trailing slash)."""
    return (uri or "").rstrip("/")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _jwt_encode(payload: Dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _jwt_decode(token: str, secret: str) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".", 2)
    except ValueError as e:
        raise ValueError("Invalid token format") from e

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64))
    return payload


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return _b64url_encode(digest)


def _get_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        return None
    if not auth_header.lower().startswith("bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip() or None


OAUTH_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"
OAUTH_SCOPES_SUPPORTED = ["memories.read", "memories.write"]
OAUTH_DEFAULT_SCOPE = " ".join(OAUTH_SCOPES_SUPPORTED)
ALLOWED_OAUTH_REDIRECT_URIS = {
    # Production connector redirect (Apps SDK docs)
    "https://chatgpt.com/connector_platform_oauth_redirect",
    # App review redirect (Apps SDK docs)
    "https://platform.openai.com/apps-manage/oauth",
}


def _www_authenticate_header(resource_metadata_url: str, scope: str = OAUTH_DEFAULT_SCOPE, **kwargs: str) -> str:
    parts = [f'Bearer resource_metadata="{resource_metadata_url}"', f'scope="{scope}"']
    for k, v in kwargs.items():
        if v is None:
            continue
        parts.append(f'{k}="{v}"')
    return ", ".join(parts)


def _unauthorized_response(request: Request, scope: str = OAUTH_DEFAULT_SCOPE, **kwargs: str) -> Response:
    base_url = _get_external_base_url(request)
    resource_metadata_url = f"{base_url}{OAUTH_RESOURCE_METADATA_PATH}"
    return Response(
        content=json.dumps({"error": "Unauthorized"}),
        status_code=401,
        media_type="application/json",
        headers={"WWW-Authenticate": _www_authenticate_header(resource_metadata_url, scope=scope, **kwargs)},
    )


def _parse_scope(scope: Optional[str]) -> List[str]:
    if not scope:
        return []
    return [s for s in str(scope).split(" ") if s]


def _verify_access_token(token: str, request: Request) -> Dict[str, Any]:
    """
    Verify our HS256 bearer access token.

    This is the resource-server validation step required by MCP authorization spec:
    signature, issuer, audience/resource, expiry, and basic shape.
    """
    secret = app_state.config.identity_secret
    payload = _jwt_decode(token, secret)

    now = int(time.time())
    if payload.get("typ") != "access_token":
        raise ValueError("Invalid token type")
    if int(payload.get("exp", 0)) < now:
        raise ValueError("Token expired")

    base_url = _get_external_base_url(request)
    expected_resource = _normalize_resource_uri(base_url)

    # Audience must be bound to this resource (RFC 8707).
    aud = _normalize_resource_uri(payload.get("aud", ""))
    if aud != expected_resource:
        raise ValueError("Invalid token audience")

    iss = _normalize_resource_uri(payload.get("iss", ""))
    if iss != expected_resource:
        raise ValueError("Invalid token issuer")

    return payload

@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    status = "healthy" if app_state.is_ready() else "initializing"
    
    # Get current session info if available
    session_id = current_session_id.get()
    session_info = {}
    if session_id and session_id in app_state.sessions:
        s = app_state.sessions[session_id]
        session_info = {
            "session_id": s.session_id,
            "authenticated": s.is_authenticated,
            "user_id": s.user_id,
        }

    return {
        "status": status,
        "initialized": app_state.is_ready(),
        "has_agent_engine": app_state.agent_engine is not None,
        "session": session_info,
        "message": "Ready" if app_state.is_ready() else "Use initialize_memory_bank to complete setup",
    }

# ========================================================================
# MCP OAuth 2.1 (MCP authorization spec: 2025-06-18)
# ========================================================================

@fastapi_app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata(request: Request) -> Dict[str, Any]:
    """
    OAuth 2.0 Protected Resource Metadata (RFC 9728), required by MCP authorization spec.

    ChatGPT uses this to discover the authorization server(s) for this MCP server.
    """
    base_url = _get_external_base_url(request)
    return {
        "resource": base_url,
        "authorization_servers": [base_url],
        "scopes_supported": OAUTH_SCOPES_SUPPORTED,
        "resource_documentation": "https://github.com/",  # optional
        "token_endpoint_auth_methods_supported": ["none"],
    }


@fastapi_app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata(request: Request) -> Dict[str, Any]:
    """
    OAuth 2.0 Authorization Server Metadata (RFC 8414), required by MCP authorization spec.
    """
    base_url = _get_external_base_url(request)
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "registration_endpoint": f"{base_url}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": OAUTH_SCOPES_SUPPORTED,
    }


@fastapi_app.post("/oauth/register")
async def oauth_register(request: Request) -> Dict[str, Any]:
    """
    Dynamic Client Registration (RFC 7591).

    ChatGPT will typically call this to obtain a client_id.
    We treat ChatGPT as a public client (PKCE, no client secret).
    """
    # We currently use a single static client id. This is sufficient for ChatGPT connectors.
    client_id = "openai-chatgpt-connector"
    return {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "client_secret_expires_at": 0,
        "token_endpoint_auth_method": "none",
        "redirect_uris": sorted(ALLOWED_OAUTH_REDIRECT_URIS),
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "scope": OAUTH_DEFAULT_SCOPE,
    }


def _sign_oauth_state(data: Dict[str, Any], secret: str) -> str:
    """
    Create an integrity-protected state blob for the upstream Google OAuth step.

    We avoid server-side session storage so the flow works even if Cloud Run scales.
    """
    payload_b64 = _b64url_encode(json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def _verify_oauth_state(state: str, secret: str) -> Dict[str, Any]:
    try:
        payload_b64, sig_b64 = state.split(".", 1)
    except ValueError as e:
        raise ValueError("Invalid state format") from e

    expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid state signature")

    data = json.loads(_b64url_decode(payload_b64))
    return data


@fastapi_app.get("/oauth/authorize")
async def oauth_authorize(request: Request) -> Response:
    """
    OAuth 2.1 authorization endpoint (authorization code + PKCE).

    ChatGPT will call this with:
    - response_type=code
    - client_id
    - redirect_uri=https://chatgpt.com/connector_platform_oauth_redirect
    - state
    - code_challenge + code_challenge_method=S256
    - resource=<canonical MCP server URI>
    """
    config = app_state.config
    if not config.google_client_id or not config.google_client_secret:
        raise HTTPException(status_code=501, detail="OAuth not configured on server")

    qp = request.query_params
    response_type = qp.get("response_type")
    client_id = qp.get("client_id")
    redirect_uri = qp.get("redirect_uri")
    state = qp.get("state")
    scope = qp.get("scope") or OAUTH_DEFAULT_SCOPE
    resource = qp.get("resource")
    code_challenge = qp.get("code_challenge")
    code_challenge_method = qp.get("code_challenge_method") or "S256"

    if response_type != "code":
        raise HTTPException(status_code=400, detail="Unsupported response_type")
    if not client_id or not redirect_uri or not state:
        raise HTTPException(status_code=400, detail="Missing required OAuth parameters")
    if redirect_uri not in ALLOWED_OAUTH_REDIRECT_URIS:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    if not resource:
        raise HTTPException(status_code=400, detail="Missing resource parameter")
    if not code_challenge or code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="PKCE S256 required")

    now = int(time.time())
    base_url = _get_external_base_url(request)
    internal_state = _sign_oauth_state(
        {
            "v": 1,
            "iat": now,
            "exp": now + 10 * 60,
            "issuer": base_url,
            "resource": _normalize_resource_uri(resource),
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        },
        config.identity_secret,
    )

    # Upstream (Google) OAuth — user authenticates with Google, we map that to our user_id.
    google_redirect_uri = config.oauth_redirect_uri or f"{base_url}/oauth/callback"
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urlencode(
            {
                "client_id": config.google_client_id,
                "redirect_uri": google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": internal_state,
                # Keep it simple: we don't need refresh tokens for this flow.
                "access_type": "online",
                "prompt": "consent",
            }
        )
    )
    return RedirectResponse(google_auth_url)


@fastapi_app.get("/oauth/callback")
async def oauth_callback(request: Request, code: str, state: str) -> Response:
    """
    Upstream (Google) OAuth callback.

    We exchange Google code -> user identity, then mint an OAuth authorization code for ChatGPT,
    and redirect the user-agent back to ChatGPT's redirect_uri with that code + original state.
    """
    config = app_state.config
    try:
        state_data = _verify_oauth_state(state, config.identity_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    now = int(time.time())
    if int(state_data.get("exp", 0)) < now:
        raise HTTPException(status_code=400, detail="State expired")

    google_redirect_uri = config.oauth_redirect_uri or f"{_get_external_base_url(request)}/oauth/callback"

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": config.google_client_id,
                "client_secret": config.google_client_secret,
                "redirect_uri": google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.error(f"OAuth token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=500, detail="Failed to exchange OAuth code")

        tokens = token_resp.json()
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch user info from Google")
        user_info = userinfo_resp.json()

    google_sub = user_info["id"]
    email = user_info.get("email")
    user_id = derive_user_id_from_google(google_sub, config.identity_secret)

    issuer = state_data.get("issuer") or _get_external_base_url(request)
    resource = state_data["resource"]

    # Mint an authorization code for ChatGPT to exchange at /oauth/token (PKCE-bound).
    auth_code = _jwt_encode(
        {
            "typ": "oauth_auth_code",
            "iss": issuer,
            "aud": resource,
            "sub": user_id,
            "email": email,
            "scope": state_data.get("scope") or OAUTH_DEFAULT_SCOPE,
            "client_id": state_data["client_id"],
            "redirect_uri": state_data["redirect_uri"],
            "code_challenge": state_data["code_challenge"],
            "code_challenge_method": state_data.get("code_challenge_method") or "S256",
            "iat": now,
            "exp": now + 5 * 60,
        },
        config.identity_secret,
    )

    redirect_uri = state_data["redirect_uri"]
    redirect_params = urlencode({"code": auth_code, "state": state_data["state"]})
    return RedirectResponse(f"{redirect_uri}?{redirect_params}")


@fastapi_app.post("/oauth/token")
async def oauth_token(request: Request) -> Dict[str, Any]:
    """
    OAuth 2.1 token endpoint (authorization_code + PKCE).

    ChatGPT exchanges `code` + `code_verifier` (and `resource`) for a bearer access token.
    """
    config = app_state.config

    # Support both form-encoded (preferred) and JSON bodies.
    content_type = (request.headers.get("content-type") or "").lower()
    data: Dict[str, Any] = {}
    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
    else:
        raw = (await request.body()).decode("utf-8")
        parsed = parse_qs(raw, keep_blank_values=True)
        data = {k: (v[0] if isinstance(v, list) and v else "") for k, v in parsed.items()}

    # Some clients may send parameters as query params; merge them as a fallback.
    qp = request.query_params
    for k in ("grant_type", "code", "client_id", "redirect_uri", "code_verifier", "resource"):
        if not data.get(k) and qp.get(k):
            data[k] = qp.get(k)

    grant_type = data.get("grant_type")
    code = data.get("code")
    client_id = data.get("client_id")
    redirect_uri = data.get("redirect_uri")
    code_verifier = data.get("code_verifier")
    resource = data.get("resource")

    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")
    if not code or not code_verifier:
        raise HTTPException(status_code=400, detail="Missing required token request parameters")

    # Log presence only (never log secrets)
    logger.info(
        "OAuth token request received: has_client_id=%s has_redirect_uri=%s has_resource=%s content_type=%s",
        bool(client_id),
        bool(redirect_uri),
        bool(resource),
        content_type,
    )

    try:
        code_payload = _jwt_decode(code, config.identity_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid code")

    now = int(time.time())
    if code_payload.get("typ") != "oauth_auth_code":
        raise HTTPException(status_code=400, detail="Invalid code type")
    if int(code_payload.get("exp", 0)) < now:
        raise HTTPException(status_code=400, detail="Code expired")

    expected_client_id = code_payload.get("client_id")
    expected_redirect_uri = code_payload.get("redirect_uri")
    expected_resource = code_payload.get("aud")

    # Compatibility: some clients omit client_id/redirect_uri/resource in token requests.
    # If provided, they must match the signed authorization code claims.
    if client_id and expected_client_id and client_id != expected_client_id:
        raise HTTPException(status_code=400, detail="client_id mismatch")
    if redirect_uri and expected_redirect_uri and redirect_uri != expected_redirect_uri:
        raise HTTPException(status_code=400, detail="redirect_uri mismatch")

    # Resource indicators must be echoed through the flow (RFC 8707).
    effective_resource = resource or expected_resource
    if not effective_resource:
        raise HTTPException(status_code=400, detail="Missing resource parameter")
    if expected_resource and _normalize_resource_uri(effective_resource) != _normalize_resource_uri(expected_resource):
        raise HTTPException(status_code=400, detail="resource mismatch")

    # PKCE verification (S256)
    if (code_payload.get("code_challenge_method") or "S256") != "S256":
        raise HTTPException(status_code=400, detail="Unsupported code_challenge_method")
    if _pkce_s256(code_verifier) != code_payload.get("code_challenge"):
        raise HTTPException(status_code=400, detail="Invalid code_verifier")

    scope = code_payload.get("scope") or OAUTH_DEFAULT_SCOPE
    access_ttl = 60 * 60  # 1 hour
    access_token = _jwt_encode(
        {
            "typ": "access_token",
            "iss": code_payload.get("iss"),
            "aud": expected_resource,
            "sub": code_payload.get("sub"),
            "email": code_payload.get("email"),
            "scope": scope,
            "iat": now,
            "exp": now + access_ttl,
        },
        config.identity_secret,
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": access_ttl,
        "scope": scope,
    }

@fastapi_app.get("/")
async def root():
    """Simple root endpoint for readiness/testing."""
    return {"status": "ok", "message": "OpenReflect MCP"}

@fastapi_app.get("/sse")
@fastapi_app.get("/sse/")
async def sse_get_endpoint(request: Request):
    """Standard MCP SSE endpoint (GET variant)."""
    if (resp := _authorize(request)) is not None:
        return resp
    return await handle_sse_connection(request)

@fastapi_app.head("/sse")
@fastapi_app.head("/sse/")
async def sse_head_endpoint(request: Request):
    """
    HEAD variant for MCP SSE endpoint.

    Some clients perform a HEAD "reachability" probe before opening the SSE stream.
    Starlette/FastAPI do not always auto-generate HEAD for streaming routes, so we
    provide it explicitly to avoid 405s.
    """
    if (resp := _authorize(request)) is not None:
        return resp
    return Response(
        status_code=200,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@fastapi_app.post("/sse")
@fastapi_app.post("/sse/")
async def sse_post_endpoint(request: Request):
    """Standard MCP SSE endpoint (POST variant)."""
    if (resp := _authorize(request)) is not None:
        return resp
    # OpenAI's connector client POSTs an initial JSON-RPC message to /sse.
    # We read it (if present) and stream the response back over SSE.
    initial_request: Optional[Dict[str, Any]] = None
    try:
        initial_request = await request.json()
    except Exception:
        initial_request = None

    return await handle_sse_connection(request, initial_request=initial_request)


# ========================================================================
# OAuth-protected SSE endpoint (for ChatGPT connector-level OAuth)
# ========================================================================

@fastapi_app.get("/sse-auth")
@fastapi_app.get("/sse-auth/")
async def sse_auth_get_endpoint(request: Request):
    """
    OAuth-protected SSE endpoint.

    Some ChatGPT connector flows probe the MCP Server URL to discover OAuth metadata.
    Returning a 401 challenge here prevents the probe from hanging on an open SSE stream.
    """
    if (resp := _authorize(request)) is not None:
        return resp

    bearer = _get_bearer_token(request)
    if not bearer:
        return _unauthorized_response(
            request,
            error="invalid_token",
            error_description="Authentication required",
        )

    try:
        token_payload = _verify_access_token(bearer, request)
    except Exception as e:
        return _unauthorized_response(
            request,
            error="invalid_token",
            error_description=str(e),
        )

    auth_context = {
        "user_id": token_payload.get("sub"),
        "email": token_payload.get("email"),
        "scopes": _parse_scope(token_payload.get("scope")),
        "auth_method": "oauth_token",
    }

    return await handle_sse_connection(request, auth_context=auth_context)


@fastapi_app.head("/sse-auth")
@fastapi_app.head("/sse-auth/")
async def sse_auth_head_endpoint(request: Request):
    """HEAD probe for the OAuth-protected SSE endpoint."""
    if (resp := _authorize(request)) is not None:
        return resp

    bearer = _get_bearer_token(request)
    if not bearer:
        return _unauthorized_response(
            request,
            error="invalid_token",
            error_description="Authentication required",
        )

    try:
        _verify_access_token(bearer, request)
    except Exception as e:
        return _unauthorized_response(
            request,
            error="invalid_token",
            error_description=str(e),
        )

    return Response(
        status_code=200,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@fastapi_app.post("/sse-auth")
@fastapi_app.post("/sse-auth/")
async def sse_auth_post_endpoint(request: Request):
    """POST variant of the OAuth-protected SSE endpoint."""
    if (resp := _authorize(request)) is not None:
        return resp

    bearer = _get_bearer_token(request)
    if not bearer:
        return _unauthorized_response(
            request,
            error="invalid_token",
            error_description="Authentication required",
        )

    try:
        token_payload = _verify_access_token(bearer, request)
    except Exception as e:
        return _unauthorized_response(
            request,
            error="invalid_token",
            error_description=str(e),
        )

    initial_request: Optional[Dict[str, Any]] = None
    try:
        initial_request = await request.json()
    except Exception:
        initial_request = None

    auth_context = {
        "user_id": token_payload.get("sub"),
        "email": token_payload.get("email"),
        "scopes": _parse_scope(token_payload.get("scope")),
        "auth_method": "oauth_token",
    }

    return await handle_sse_connection(
        request,
        initial_request=initial_request,
        auth_context=auth_context,
    )

async def handle_sse_connection(
    request: Request,
    initial_request: Optional[Dict[str, Any]] = None,
    auth_context: Optional[Dict[str, Any]] = None,
):
    """Shared handler for SSE connection."""
    
    # Simple unique session ID
    session_id = str(uuid.uuid4())
    current_session_id.set(session_id)
    session = app_state.get_or_create_session(session_id)

    # If an OAuth bearer token was presented to /sse-auth, bind it to this in-process
    # session as a compatibility measure and set auth metadata.
    if auth_context and auth_context.get("user_id"):
        session.user_id = auth_context.get("user_id")
        session.email = auth_context.get("email")
        session.auth_method = auth_context.get("auth_method") or "oauth_token"
        session.authenticated_at = datetime.utcnow()

    async def event_stream(
        initial_request: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        # Ensure context variable is set in the generator task
        current_session_id.set(session_id)

        # Propagate bearer-auth identity into the SSE generator context (critical for
        # initial tool calls delivered via POST /sse-auth).
        if auth_context and auth_context.get("user_id"):
            current_user_id.set(auth_context.get("user_id"))
            current_user_email.set(auth_context.get("email"))
            current_user_scopes.set(auth_context.get("scopes") or [])
        else:
            current_user_id.set(None)
            current_user_email.set(None)
            current_user_scopes.set(None)
        
        try:
            logger.info(f"New SSE session: {session_id}")

            queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
            _sse_sessions[session_id] = queue

            base_url = _get_external_base_url(request)
            message_endpoint = f"{base_url}/message?session_id={session_id}"
            
            yield f"event: endpoint\ndata: {message_endpoint}\n\n"

            if initial_request:
                if (initial_resp := await _handle_jsonrpc(initial_request)) is not None:
                    await queue.put(initial_resp)

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15)
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
            _sse_sessions.pop(session_id, None)
            # Sessions are kept in app_state.sessions for identity persistence 
            # while the process lives, but SSE cleanup is handled here.

    return StreamingResponse(
        event_stream(initial_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

async def _handle_jsonrpc(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a JSON-RPC 2.0 request and return a JSON-RPC response object.

    Returns None for notifications that require no response.
    """
    # Check for JSON-RPC 2.0 structure
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        raise ValueError("Invalid JSON-RPC request")

    method = body.get("method")
    msg_id = body.get("id")
    params = body.get("params", {})

    logger.info(f"Received message: method={method} id={msg_id}")

    # Manual routing to FastMCP methods
    result = None
    error = None

    if method == "ping":
        result = {}
        
    elif method == "initialize":
        requested_protocol_version: Optional[str] = None
        if isinstance(params, dict):
            requested_protocol_version = params.get("protocolVersion")

        protocol_version = requested_protocol_version or "2024-11-05"
        if requested_protocol_version and requested_protocol_version != protocol_version:
            logger.info(
                "Client requested protocolVersion=%s; responding with %s",
                requested_protocol_version,
                protocol_version,
            )
        else:
            logger.info("Initialize requested protocolVersion=%s", protocol_version)

        result = {
            # Echo the client's requested protocolVersion when provided to maximize
            # compatibility with strict clients.
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {"listChanged": False},
                # Some OpenAI clients assume `resources` exists in capabilities.
                # We advertise an empty/unsupported resources surface and implement
                # `resources/list` as an empty list for compatibility.
                "resources": {"listChanged": False, "subscribe": False},
                "logging": {},
            },
            "serverInfo": {
                "name": mcp_server.name,
                "version": "0.1.0"
            }
        }

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        tools = await mcp_server.list_tools()
        tools_payload = tools.model_dump() if hasattr(tools, "model_dump") else tools
        if isinstance(tools_payload, dict) and "tools" in tools_payload:
            result = tools_payload
        elif isinstance(tools_payload, list):
            result = {"tools": tools_payload}
        else:
            result = {"tools": tools_payload}

    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        
        tool_result = await mcp_server.call_tool(name, args)
        if (
            isinstance(tool_result, (list, tuple))
            and len(tool_result) == 2
            and isinstance(tool_result[0], list)
        ):
            result = {"content": tool_result[0]}
        elif hasattr(tool_result, "model_dump"):
            result = tool_result.model_dump()
        else:
            result = tool_result
            
    elif method == "prompts/list":
        prompts = await mcp_server.list_prompts()
        prompts_payload = (
            prompts.model_dump() if hasattr(prompts, "model_dump") else prompts
        )
        if isinstance(prompts_payload, dict) and "prompts" in prompts_payload:
            result = prompts_payload
        elif isinstance(prompts_payload, list):
            result = {"prompts": prompts_payload}
        else:
            result = {"prompts": prompts_payload}
            
    elif method == "prompts/get":
        name = params.get("name")
        args = params.get("arguments", {})
        prompt_result = await mcp_server.get_prompt(name, args)
        if hasattr(prompt_result, "model_dump"):
            result = prompt_result.model_dump()
        else:
            result = prompt_result

    elif method == "resources/list":
        # Return no resources (we don't expose resources today), but avoid client crashes.
        result = {"resources": []}

    elif method == "resources/read":
        error = {"code": -32601, "message": "Method not found: resources/read"}

    elif method == "resources/subscribe":
        error = {"code": -32601, "message": "Method not found: resources/subscribe"}

    elif method == "resources/unsubscribe":
        error = {"code": -32601, "message": "Method not found: resources/unsubscribe"}

    else:
        error = {"code": -32601, "message": f"Method not found: {method}"}

    response: Dict[str, Any] = {"jsonrpc": "2.0"}
    if msg_id is not None:
        response["id"] = msg_id

    if error:
        response["error"] = error
    else:
        response["result"] = result
    return response

@fastapi_app.post("/message")
async def message_endpoint(request: Request, session_id: str = None):
    """
    Handle JSON-RPC messages from the client.
    """
    if (resp := _authorize(request)) is not None:
        return resp

    # Set the current session ID for this request context
    if session_id:
        current_session_id.set(session_id)

    # Clear per-request auth context (defensive; ContextVars are per-task but keep it explicit)
    current_user_id.set(None)
    current_user_email.set(None)
    current_user_scopes.set(None)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Enforce transport-level OAuth for tool invocations unless a per-call `key` is provided.
    # This aligns with MCP authorization spec: clients must send Authorization header on every request
    # once authenticated, but we allow a legacy "key" path for non-ChatGPT clients.
    if isinstance(body, dict) and body.get("method") == "tools/call":
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}

        bearer = _get_bearer_token(request)
        if bearer:
            try:
                token_payload = _verify_access_token(bearer, request)
            except Exception as e:
                return _unauthorized_response(
                    request,
                    error="invalid_token",
                    error_description=str(e),
                )

            current_user_id.set(token_payload.get("sub"))
            current_user_email.set(token_payload.get("email"))
            current_user_scopes.set(_parse_scope(token_payload.get("scope")))

        elif args.get("key"):
            # Allow key-based identity; tools will derive user_id from the key.
            pass
        else:
            return _unauthorized_response(
                request,
                error="invalid_token",
                error_description="Authentication required",
            )

    try:
        resp = await _handle_jsonrpc(body)

        # If this request is associated with an active SSE session, deliver the
        # response over SSE and return a small ack.
        if session_id and session_id in _sse_sessions:
            if resp is not None:
                await _sse_sessions[session_id].put(resp)
            return Response(status_code=202)

        # Fallback: no SSE session found, return JSON-RPC response directly.
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