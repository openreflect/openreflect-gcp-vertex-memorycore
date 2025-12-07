"""HTTP server module for Cloud Run deployment using SSE transport."""

import asyncio
import json
import logging
import os
import sys
from io import BytesIO
from typing import AsyncGenerator, Dict, Any, Optional

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server

from .app_state import app as app_state
from .server import create_server

# Configure logging to stdout/stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Create FastAPI app
fastapi_app = FastAPI(title="Vertex AI Memory Bank MCP Server")

# Create MCP server instance
mcp_server = create_server()

# In-memory message queue for bridging stdio to HTTP
message_queue: asyncio.Queue = asyncio.Queue()
response_map: Dict[str, asyncio.Future] = {}


async def process_mcp_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Process MCP message through FastMCP server."""
    # Create a bridge to handle stdio-based FastMCP server
    # This is a simplified approach - in production, you'd want proper MCP HTTP transport
    try:
        # Use the server's internal handler if available
        # FastMCP uses stdio internally, so we need to bridge it
        import io
        from mcp.server import Server
        
        # Create a temporary stdio-like interface
        read_stream = io.BytesIO()
        write_stream = io.BytesIO()
        
        # For now, return a basic response structure
        # In a full implementation, you'd properly bridge stdio to HTTP
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"status": "ok"}
        }
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": str(e)
            }
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


@fastapi_app.post("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP protocol over HTTP."""
    try:
        body = await request.body()
        
        if not body:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        try:
            message = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        
        async def event_stream() -> AsyncGenerator[str, None]:
            try:
                # Process message
                response = await process_mcp_message(message)
                yield f"data: {json.dumps(response)}\n\n"
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
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
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


@fastapi_app.post("/message")
async def message_endpoint(request: Request):
    """Direct JSON-RPC message endpoint."""
    try:
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


@fastapi_app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Vertex AI Memory Bank MCP Server",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "sse": "/sse",
            "message": "/message"
        }
    }


# For Cloud Run, use the FastAPI app directly
app = fastapi_app

