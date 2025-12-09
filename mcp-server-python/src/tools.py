"""MCP Tools"""

import logging
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

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register all MCP tools with the server."""

    # ========================================================================
    # Configuration Tools
    # ========================================================================

    @mcp.tool()
    async def initialize_memory_bank(
        project_id: str,
        location: str = "us-central1",
        memory_topics: Optional[List[str]] = None,
        agent_engine_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initialize Memory Bank with your Google Cloud project.

        This is the first function you should call to set up the connection.

        Args:
            project_id: Your Google Cloud project ID
            location: Google Cloud location (default: us-central1)
            memory_topics: Optional list of topics:
                - USER_PREFERENCES: User preferences and settings
                - USER_PERSONAL_INFO: Personal information
                - KEY_CONVERSATION_DETAILS: Important events
                - EXPLICIT_INSTRUCTIONS: Explicit remember/forget requests
            agent_engine_name: Optional existing Agent Engine name to reuse.
                              If not provided, creates a new one.

        Returns:
            Status and configuration details

        Example:
            await initialize_memory_bank(
                project_id="my-project",
                memory_topics=["USER_PREFERENCES", "USER_PERSONAL_INFO"]
            )
        """
        try:
            logger.info(f"Initializing Memory Bank for project {project_id}")

            # Create Vertex AI client
            client = vertexai.Client(project=project_id, location=location)

            # Build configuration if topics provided
            config = {}
            if memory_topics:
                config["customization_configs"] = [
                    {
                        "memory_topics": [
                            {"managed_memory_topic": {"managed_topic_enum": topic}}
                            for topic in memory_topics
                        ]
                    }
                ]

            # Use existing or create new Agent Engine
            if agent_engine_name:
                # Reuse specified engine
                agent_engine = client.agent_engines.get(name=agent_engine_name)
                logger.info(
                    f"Using specified Agent Engine: {agent_engine.api_resource.name}"
                )
            else:
                # Always create a new Agent Engine with Memory Bank
                agent_engine = client.agent_engines.create(
                    config=(
                        {"context_spec": {"memory_bank_config": config}}
                        if config
                        else None
                    )
                )
                logger.info(
                    f"Created new Agent Engine: {agent_engine.api_resource.name}"
                )

            # Update app state
            app.client = client
            app.agent_engine = agent_engine
            app.config.project_id = project_id
            app.config.location = location
            app.initialized = True

            return format_success_response(
                {
                    "agent_engine_name": agent_engine.api_resource.name,
                    "project_id": project_id,
                    "location": location,
                }
            )

        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return format_error_response(str(e))

    # ========================================================================
    # Memory Generation Tools
    # ========================================================================

    @mcp.tool()
    async def generate_memories(
        conversation: List[Dict[str, str]],
        scope: Dict[str, str],
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate memories from a conversation.

        Analyzes conversation and extracts relevant information to remember.

        Args:
            conversation: List of messages with 'role' and 'content'
            scope: Dictionary identifying the user (e.g., {"user_id": "123"})
            wait_for_completion: Whether to wait for generation to complete

        Returns:
            Generated memories and operation status

        Example:
            conversation = [
                {"role": "user", "content": "I'm Alice and I love Python"},
                {"role": "assistant", "content": "Nice to meet you, Alice!"}
            ]
            await generate_memories(conversation, {"user_id": "alice123"})
        """
        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        # Validate inputs
        if error := validate_scope(scope):
            return format_error_response(error)

        if error := validate_conversation(conversation):
            return format_error_response(error)

        try:
            # Convert conversation to events
            events = format_conversation_events(conversation)

            # Generate memories
            operation = app.client.agent_engines.generate_memories(
                name=app.agent_engine.api_resource.name,
                direct_contents_source={"events": events},
                scope=scope,
                config={"wait_for_completion": wait_for_completion},
            )

            logger.info(f"Generated memories for scope {scope}")

            # Format response
            result = {
                "operation_name": operation.name,
                "done": operation.done,
                "scope": scope,
            }

            # Include generated memories if operation completed
            if operation.done and hasattr(operation, "response"):
                # Try different possible attribute names for API compatibility
                generated_mems = None
                if hasattr(operation.response, "generatedMemories"):
                    generated_mems = operation.response.generatedMemories
                elif hasattr(operation.response, "generated_memories"):
                    generated_mems = operation.response.generated_memories

                if generated_mems:
                    result["generated_memories"] = [
                        {
                            "action": getattr(mem, "action", None),
                            "fact": (
                                getattr(getattr(mem, "memory", None), "fact", None)
                                if hasattr(mem, "memory")
                                else getattr(mem, "fact", None)
                            ),
                        }
                        for mem in generated_mems
                    ]

            return format_success_response(result)

        except Exception as e:
            logger.error(f"Failed to generate memories: {e}")
            return format_error_response(str(e))

    # ========================================================================
    # Memory Retrieval Tools
    # ========================================================================

    @mcp.tool()
    async def retrieve_memories(
        scope: Dict[str, str], search_query: Optional[str] = None, top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve memories for a user, with optional similarity search.

        Args:
            scope: User identifier dictionary
            search_query: Optional search query for similarity matching
            top_k: Number of results to return (default: 5)

        Returns:
            List of memories with optional similarity scores

        Examples:
            # Get all memories for a user
            await retrieve_memories({"user_id": "alice123"})

            # Search for specific memories
            await retrieve_memories(
                {"user_id": "alice123"},
                search_query="programming preferences",
                top_k=3
            )
        """
        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        # Validate scope
        if error := validate_scope(scope):
            return format_error_response(error)

        try:
            # Retrieve memories
            if search_query:
                # Similarity search
                results = app.client.agent_engines.retrieve_memories(
                    name=app.agent_engine.api_resource.name,
                    scope=scope,
                    similarity_search_params={
                        "search_query": search_query,
                        "top_k": top_k,
                    },
                )
                logger.info(f"Searched memories for {scope} with query: {search_query}")
            else:
                # Get all memories for scope
                results = app.client.agent_engines.retrieve_memories(
                    name=app.agent_engine.api_resource.name, scope=scope
                )
                logger.info(f"Retrieved all memories for {scope}")

            # Format memories
            memories = []
            for retrieved in list(results):
                memory_data = format_memory(retrieved.memory)
                if search_query and hasattr(retrieved, "distance"):
                    memory_data["similarity_score"] = retrieved.distance
                memories.append(memory_data)

            return format_success_response(
                {"scope": scope, "memories_count": len(memories), "memories": memories}
            )

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return format_error_response(str(e))

    # ========================================================================
    # Memory Management Tools
    # ========================================================================

    @mcp.tool()
    async def create_memory(
        fact: str, scope: Dict[str, str], ttl_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a memory directly.

        Args:
            fact: The information to remember
            scope: User identifier
            ttl_seconds: Optional time-to-live in seconds

        Returns:
            Created memory details

        Example:
            await create_memory(
                fact="Alice prefers dark mode in all applications",
                scope={"user_id": "alice123"},
                ttl_seconds=86400  # Expires in 24 hours
            )
        """
        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        # Validate inputs
        if error := validate_memory_fact(fact):
            return format_error_response(error)

        if error := validate_scope(scope):
            return format_error_response(error)

        try:
            # Build memory data
            memory_data = {"fact": fact.strip(), "scope": scope}

            # Add expiration if TTL provided
            if ttl_seconds and ttl_seconds > 0:
                memory_data["expire_time"] = format_ttl_expiration(ttl_seconds)

            # Create memory with correct API
            operation = app.client.agent_engines.create_memory(
                name=app.agent_engine.api_resource.name,
                fact=fact,
                scope=scope,
                config=(
                    {"expire_time": memory_data.get("expire_time")}
                    if "expire_time" in memory_data
                    else None
                ),
            )

            # Extract the actual memory from the operation response
            if operation.response:
                memory = operation.response
            else:
                # If not done yet, return operation info
                memory = operation

            logger.info(f"Created memory for {scope}")

            return format_success_response({"memory": format_memory(memory)})

        except Exception as e:
            logger.error(f"Failed to create memory: {e}")
            return format_error_response(str(e))

    @mcp.tool()
    async def delete_memory(memory_name: str) -> Dict[str, Any]:
        """
        Delete a specific memory by name.

        Args:
            memory_name: Full memory resource name

        Returns:
            Deletion confirmation
        """
        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        try:
            app.client.agent_engines.delete_memory(name=memory_name)
            logger.info(f"Deleted memory: {memory_name}")

            return format_success_response({"deleted": memory_name})
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return format_error_response(str(e))

    @mcp.tool()
    async def list_memories(page_size: int = 50) -> Dict[str, Any]:
        """
        List all memories in the Memory Bank.

        Args:
            page_size: Number of memories per page (default: 50)

        Returns:
            List of all memories
        """
        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        try:
            pager = app.client.agent_engines.list_memories(
                name=app.agent_engine.api_resource.name,
                config={"page_size": page_size} if page_size else None,
            )

            # Convert iterator to list and format
            memories = []
            for memory in pager:
                logger.debug(f"Processing memory: {memory}")
                formatted = format_memory(memory)
                logger.debug(f"Formatted memory: {formatted}")
                memories.append(formatted)

            logger.info(f"Listed {len(memories)} memories")

            return format_success_response(
                {"count": len(memories), "memories": memories}
            )

        except Exception as e:
            logger.error(f"Failed to list memories: {e}")
            return format_error_response(str(e))
