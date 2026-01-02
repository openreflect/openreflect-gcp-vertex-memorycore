"""Main server module - Orchestrates the MCP server."""

import logging
import os
import sys
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .app_state import app
from .config import Config
from .prompts import register_prompts
from .tools import register_tools

# Configure logging to stderr (MCP uses stdout for protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """
    Manage application lifecycle.
    
    Simple startup and shutdown logic following "Simple is better than complex".
    """
    # Startup
    logger.info("Starting Memory Bank MCP Server")
    
    # Load configuration from environment
    app.config = Config.from_env()

    # NOTE: We intentionally defer Vertex AI network initialization until the first
    # memory tool call. This keeps cold starts fast and prevents connector OAuth
    # configuration timeouts in clients like ChatGPT.
    #
    # Memory tools call a lazy initializer that:
    # - creates vertexai.Client
    # - loads AGENT_ENGINE_NAME when set
    # - otherwise requires initialize_memory_bank
    app.initialized = app.config.is_valid()
    if app.initialized:
        logger.info("Config loaded from environment (Vertex init deferred until first tool call)")
    else:
        logger.info("No configuration found - use initialize_memory_bank to get started")
    
    yield app
    
    # Shutdown
    logger.info("Shutting down Memory Bank MCP Server")


def create_server() -> FastMCP:
    """
    Create and configure the MCP server.
    
    Returns:
        Configured FastMCP server instance
    """
    # Create the server
    mcp = FastMCP(
        "OpenReflect MCP",
        lifespan=lifespan
    )
    
    # Register all tools and prompts
    register_tools(mcp)
    register_prompts(mcp)
    
    logger.info("Server configured with all tools and prompts")
    
    return mcp


def run():
    """Run the Memory Bank MCP server."""
    try:
        server = create_server()
        server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


def run_http():
    """Run the Memory Bank MCP server in HTTP mode."""
    import uvicorn
    from .server_http import app
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")