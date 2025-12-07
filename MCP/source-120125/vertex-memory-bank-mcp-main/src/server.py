"""Main server module - Orchestrates the MCP server."""

import logging
import sys
from contextlib import asynccontextmanager

import vertexai
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
    
    # Try to initialize Vertex AI client if configured
    if app.config.is_valid():
        try:
            app.client = vertexai.Client(
                project=app.config.project_id,
                location=app.config.location,
            )
            app.initialized = True
            logger.info("Vertex AI client initialized from environment")
        except Exception as e:
            logger.warning(f"Could not initialize Vertex AI client: {e}")
            logger.info("Server running - use initialize_memory_bank to set up")
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
        "Vertex AI Memory Bank",
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