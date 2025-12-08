"""HTTP server module for Cloud Run deployment using SSE transport."""

import asyncio
import json
import logging
import os
import sys
import subprocess
import uuid
from typing import AsyncGenerator, Dict, Any, Optional

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .app_state import app as app_state

# Configure logging to stdout/stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Create FastAPI app
fastapi_app = FastAPI(title="Vertex AI Memory Bank MCP Server")

# Basic CORS to support browser-based connector flows (adjust origins if needed)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional bearer token for connector-facing auth (distinct from GCP IAM)
CONNECTOR_BEARER_TOKEN = os.getenv("CONNECTOR_BEARER_TOKEN")

# Global subprocess for stdio bridge
_stdio_process: Optional[subprocess.Popen] = None
_stdio_lock = asyncio.Lock()


async def get_stdio_process() -> subprocess.Popen:
    """Get or create the stdio subprocess for MCP server."""
    global _stdio_process
    
    async with _stdio_lock:
        if _stdio_process is None or _stdio_process.poll() is not None:
            # Start the stdio server as a subprocess
            server_path = os.path.join(os.path.dirname(__file__), "..", "memory_bank_server.py")
            _stdio_process = subprocess.Popen(
                [sys.executable, server_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )
            logger.info("Started MCP stdio server subprocess")
        
        return _stdio_process


async def process_mcp_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Process MCP message through FastMCP server via stdio bridge."""
    try:
        process = await get_stdio_process()
        
        # Send message to stdio server
        message_json = json.dumps(message) + "\n"
        process.stdin.write(message_json)
        process.stdin.flush()
        
        # Read response (with timeout)
        try:
            response_line = await asyncio.wait_for(
                asyncio.to_thread(process.stdout.readline),
                timeout=30.0
            )
            
            if not response_line:
                raise Exception("No response from MCP server")
            
            response = json.loads(response_line.strip())
            return response
            
        except asyncio.TimeoutError:
            raise Exception("Timeout waiting for MCP server response")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
            
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": message.get("id") if isinstance(message, dict) else None,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }


def _authorize(request: Request) -> Optional[Response]:
    """Optional bearer token auth for connector-facing endpoints."""
    if not CONNECTOR_BEARER_TOKEN:
        return None

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


def _cors_headers() -> Dict[str, str]:
    """Standard headers for SSE and JSON responses."""
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    if app_state.is_ready():
        return {"status": "healthy", "initialized": True}
    elif app_state.config.is_valid():
        return Response(
            content=json.dumps({"status": "initializing", "initialized": False}),
            status_code=503,
            media_type="application/json"
        )
    else:
        return Response(
            content=json.dumps({"status": "not_configured", "initialized": False}),
            status_code=503,
            media_type="application/json"
        )


async def _sse_handler(request: Request):
    """Shared SSE handler to support multiple endpoint paths."""
    try:
        # Optional auth
        if (resp := _authorize(request)) is not None:
            return resp

        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Empty request body")

        try:
            message = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

        request_id = str(uuid.uuid4())
        logger.info(f"SSE request {request_id}: method={message.get('method')}")

        async def event_stream() -> AsyncGenerator[str, None]:
            try:
                # Initial keepalive/handshake event
                yield f"event: open\ndata: {json.dumps({'request_id': request_id})}\n\n"

                response = await process_mcp_message(message)
                yield f"data: {json.dumps(response)}\n\n"

                # Graceful close event for clients that expect explicit end
                yield f"event: close\ndata: {json.dumps({'request_id': request_id, 'status': 'done'})}\n\n"
            except Exception as e:
                logger.error(f"Error in SSE stream: {e}", exc_info=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id") if isinstance(message, dict) else None,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
                yield f"data: {json.dumps(error_response)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers=_cors_headers(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in SSE endpoint: {e}", exc_info=True)
        return Response(
            content=json.dumps({"error": str(e)}),
            status_code=500,
            media_type="application/json"
        )


@fastapi_app.post("/sse")
async def sse_endpoint(request: Request):
    """Legacy SSE endpoint for MCP protocol over HTTP."""
    return await _sse_handler(request)


@fastapi_app.post("/mcp/stream")
async def mcp_stream_endpoint(request: Request):
    """ChatGPT-compatible SSE endpoint."""
    return await _sse_handler(request)


@fastapi_app.post("/message")
async def message_endpoint(request: Request):
    """Direct JSON-RPC message endpoint."""
    try:
        if (resp := _authorize(request)) is not None:
            return resp

        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        message = json.loads(body.decode('utf-8'))
        response = await process_mcp_message(message)
        
        return response
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except Exception as e:
        logger.error(f"Error in message endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/manifest")
async def manifest():
    """Simple manifest for connector discovery."""
    return {
        "name": "vertex-memory-bank-mcp",
        "version": "0.1.0",
        "transport": "sse",
        "description": "Vertex AI Memory Bank MCP server with HTTPS/SSE transport",
        "endpoints": {
            "sse": "/sse",
            "mcp_stream": "/mcp/stream",
            "message": "/message",
            "health": "/health",
        },
        "tools": [
            "initialize_memory_bank",
            "generate_memories",
            "retrieve_memories",
            "create_memory",
            "delete_memory",
            "list_memories",
        ],
    }


@fastapi_app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Vertex AI Memory Bank MCP Server",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "sse": "/sse",
            "mcp_stream": "/mcp/stream",
            "message": "/message",
            "manifest": "/manifest",
        },
        "auth": "connector bearer token required" if CONNECTOR_BEARER_TOKEN else "no auth enforced",
    }


@fastapi_app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _stdio_process
    if _stdio_process:
        try:
            _stdio_process.terminate()
            try:
                _stdio_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _stdio_process.kill()
            logger.info("Stopped MCP stdio server subprocess")
        except Exception as e:
            logger.error(f"Error stopping subprocess: {e}")


# For Cloud Run, use the FastAPI app directly
app = fastapi_app

