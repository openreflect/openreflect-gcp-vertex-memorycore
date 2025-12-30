"""HTTP server module for Cloud Run deployment using SSE transport."""

import asyncio
from dataclasses import asdict, is_dataclass
import json
import logging
import os
import sys
import uuid
import base64
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse
import mcp.types as types

# Import the server creation factory directly
from .server import create_server
from .app_state import app as app_state, SessionState, current_session_id
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
# OAuth Endpoints (AUTH_DESIGN.md)
# ========================================================================

def encode_state(session_id: str) -> str:
    """Encode session_id for OAuth state parameter."""
    return base64.urlsafe_b64encode(
        json.dumps({"session_id": session_id}).encode()
    ).decode()

def decode_state(state: str) -> str:
    """Decode session_id from OAuth state parameter."""
    data = json.loads(base64.urlsafe_b64decode(state))
    return data["session_id"]

@fastapi_app.get("/oauth/authorize")
async def oauth_authorize(session_id: str):
    """Initiate Google OAuth flow."""
    config = app_state.config
    if not config.google_client_id or not config.google_client_secret:
        raise HTTPException(status_code=501, detail="OAuth not configured on server")
    
    state = encode_state(session_id)
    redirect_uri = config.oauth_redirect_uri or "https://openreflect.run.app/oauth/callback"
    
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={config.google_client_id}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        "scope=email%20profile%20openid&"
        "access_type=offline&"
        f"state={state}"
    )
    return RedirectResponse(auth_url)

@fastapi_app.get("/oauth/callback")
async def oauth_callback(code: str, state: str):
    """Handle Google OAuth callback."""
    config = app_state.config
    try:
        session_id = decode_state(state)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    redirect_uri = config.oauth_redirect_uri or "https://openreflect.run.app/oauth/callback"

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": config.google_client_id,
                "client_secret": config.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
        )
        if token_resp.status_code != 200:
            logger.error(f"OAuth token exchange failed: {token_resp.text}")
            raise HTTPException(status_code=500, detail="Failed to exchange OAuth code")
        
        tokens = token_resp.json()
        
        # Get user info
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch user info from Google")
        
        user_info = userinfo_resp.json()

    # Derive user_id and bind to session
    google_sub = user_info["id"]
    email = user_info.get("email")
    user_id = derive_user_id_from_google(google_sub, config.identity_secret)
    
    session = app_state.get_or_create_session(session_id)
    session.user_id = user_id
    session.email = email
    session.auth_method = "oauth"
    session.authenticated_at = datetime.utcnow()
    
    logger.info(f"OAuth success for user {email} (session {session_id})")

    # Return success page (as specified in AUTH_DESIGN.md)
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OpenReflect - Connected!</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white;
            }}
            .container {{ text-align: center; padding: 2rem; }}
            .checkmark {{ font-size: 4rem; margin-bottom: 1rem; color: #4CAF50; }}
            h1 {{ margin-bottom: 0.5rem; }}
            p {{ color: #a0a0a0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="checkmark">✓</div>
            <h1>Connected to OpenReflect!</h1>
            <p>Signed in as {email or 'User'}</p>
            <p>You can close this window and return to your AI assistant.</p>
        </div>
        <script>setTimeout(() => window.close(), 3000);</script>
    </body>
    </html>
    """)

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

async def handle_sse_connection(
    request: Request,
    initial_request: Optional[Dict[str, Any]] = None,
):
    """Shared handler for SSE connection."""

    def _first_forwarded_value(value: Optional[str]) -> Optional[str]:
        """Return the first comma-separated value from a forwarded header."""
        if not value:
            return None
        return value.split(",")[0].strip()

    def _get_external_base_url(request: Request) -> str:
        """Construct an externally-reachable base URL."""
        proto = _first_forwarded_value(request.headers.get("x-forwarded-proto"))
        host = (
            _first_forwarded_value(request.headers.get("x-forwarded-host"))
            or request.headers.get("host")
        )
        if proto and host:
            return f"{proto}://{host}".rstrip("/")
        return str(request.base_url).rstrip("/")
    
    # Simple unique session ID
    session_id = str(uuid.uuid4())
    current_session_id.set(session_id)
    app_state.get_or_create_session(session_id)

    async def event_stream(
        initial_request: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        # Ensure context variable is set in the generator task
        current_session_id.set(session_id)
        
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

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

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