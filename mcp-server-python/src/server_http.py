"""HTTP server module for Cloud Run deployment using SSE transport."""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse
import mcp.types as types

# Import the server creation factory directly
from .server import create_server
from .app_state import app as app_state

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize the MCP server instance globally
mcp_server = create_server()

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
fastapi_app = FastAPI(title="Vertex AI Memory Bank MCP Server", lifespan=lifespan)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    message = (
        "Ready"
        if app_state.is_ready()
        else "Use initialize_memory_bank to complete setup or set AGENT_ENGINE_NAME"
    )
    return {
        "status": status,
        "initialized": app_state.is_ready(),
        "has_agent_engine": app_state.agent_engine is not None,
        "message": message,
    }

@fastapi_app.get("/")
async def root():
    """Simple root endpoint for readiness/testing."""
    return {"status": "ok", "message": "Vertex AI Memory Bank MCP"}

@fastapi_app.get("/sse")
@fastapi_app.get("/sse/")
async def sse_get_endpoint(request: Request):
    """Standard MCP SSE endpoint (GET variant)."""
    if (resp := _authorize(request)) is not None:
        return resp
    return await handle_sse_connection(request)

@fastapi_app.post("/sse")
@fastapi_app.post("/sse/")
async def sse_post_endpoint(request: Request):
    """Standard MCP SSE endpoint (POST variant)."""
    if (resp := _authorize(request)) is not None:
        return resp
    return await handle_sse_connection(request)

async def handle_sse_connection(request: Request):
    """Shared handler for SSE connection."""
    
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Simple unique session ID
            session_id = str(uuid.uuid4())
            logger.info(f"New SSE session: {session_id}")

            # Construct the absolute URL for the /message endpoint
            # We use the request's base URL + /message
            # We also append session_id for tracking
            message_endpoint = f"{request.base_url}message?session_id={session_id}"
            
            # The MCP spec says the first event is the endpoint URL
            yield f"event: endpoint\ndata: {message_endpoint}\n\n"

            # Keep the connection open with keepalives
            while True:
                await asyncio.sleep(15)
                yield ": keepalive\n\n"
                
        except asyncio.CancelledError:
            logger.info(f"SSE session disconnected: {session_id}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@fastapi_app.post("/message")
async def message_endpoint(request: Request, session_id: str = None):
    """
    Handle JSON-RPC messages from the client.
    """
    if (resp := _authorize(request)) is not None:
        return resp

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
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
            # Handle initialize request
            # MCP clients send this first. FastMCP usually handles it.
            # We return server capabilities.
            result = {
                "protocolVersion": "2024-12-01",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "prompts": {"listChanged": False},
                    "resources": {"listChanged": False, "subscribe": False},
                    "logging": {},
                },
                "serverInfo": {
                    "name": mcp_server.name,
                    "version": "0.1.0"
                }
            }

        elif method == "notifications/initialized":
            # Client confirming initialization
            # No response needed for notification
            return Response(status_code=200)

        elif method == "tools/list":
            tools = await mcp_server.list_tools()
            # tools is usually a Pydantic model or dict
            # We need to ensure it's serializable
            if hasattr(tools, "model_dump"):
                 result = tools.model_dump()
            else:
                 result = tools

        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            
            # call_tool returns a CallToolResult usually
            tool_result = await mcp_server.call_tool(name, args)
            
            if hasattr(tool_result, "model_dump"):
                result = tool_result.model_dump()
            else:
                result = tool_result
                
        elif method == "prompts/list":
            prompts = await mcp_server.list_prompts()
            if hasattr(prompts, "model_dump"):
                result = prompts.model_dump()
            else:
                result = prompts
                
        elif method == "prompts/get":
            name = params.get("name")
            args = params.get("arguments", {})
            prompt_result = await mcp_server.get_prompt(name, args)
            if hasattr(prompt_result, "model_dump"):
                result = prompt_result.model_dump()
            else:
                result = prompt_result

        else:
            # Method not found
            error = {"code": -32601, "message": f"Method not found: {method}"}

        # Construct response
        response = {
            "jsonrpc": "2.0",
            "id": msg_id
        }
        
        if error:
            response["error"] = error
        else:
            response["result"] = result
            
        return response

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0", 
            "id": body.get("id"), 
            "error": {"code": -32603, "message": str(e)}
        }

# For Cloud Run, use the FastAPI app directly
app = fastapi_app