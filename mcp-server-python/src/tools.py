"""MCP Tools"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import vertexai
from mcp.server.fastmcp import FastMCP

from .app_state import app, current_session_id, SessionState
from .auth import derive_user_id_from_key
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

    def _get_session() -> SessionState:
        """Helper to get current session state."""
        session_id = current_session_id.get()
        return app.get_or_create_session(session_id)

    def _get_user_id(key: str = None) -> tuple[str, str]:
        """
        Get user_id from key (stateless) or session (stateful).
        Returns (user_id, error_message). If error_message is set, user_id is None.
        """
        if key:
            # Stateless auth: derive user_id from key
            if len(key.strip()) < 4:
                return None, "Passphrase must be at least 4 characters."
            user_id = derive_user_id_from_key(key, app.config.identity_secret)
            return user_id, None
        else:
            # Stateful auth: check session
            session = _get_session()
            if session.is_authenticated:
                return session.user_id, None
            return None, "Please provide a key or connect your account first."

    # ========================================================================
    # Authentication Tools (AUTH_DESIGN.md)
    # ========================================================================

    @mcp.tool()
    async def connect_account(request: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Connect your Google account to access your memories across AI assistants.
        
        This returns an OAuth link. Once you sign in, your memories will be
        accessible from ChatGPT, Claude, and any other client using OpenReflect.
        """
        session = _get_session()
        if session.is_authenticated:
            return format_success_response(
                {
                    "status": "already_connected",
                    "email": session.email,
                    "auth_method": session.auth_method,
                },
                message="Your account is already connected!"
            )

        # In a real Cloud Run deployment, we'd use the actual service URL.
        # For MVP, we'll try to guess it or use a placeholder if not set in config.
        # The client should ideally know the base URL.
        auth_url = f"/oauth/authorize?session_id={session.session_id}"
        
        return format_success_response(
            {
                "status": "auth_required",
                "auth_url": auth_url,
            },
            message="Please visit the auth_url to sign in with Google."
        )

    @mcp.tool()
    async def connect_with_key(key: str) -> Dict[str, Any]:
        """
        Connect using a key instead of Google sign-in.
        
        Use the same key across all AI assistants to access the same memories.
        
        Args:
            key: A memorable phrase (at least 4 characters)
        """
        if not key or len(key.strip()) < 4:
            return format_error_response("Key must be at least 4 characters.")

        session = _get_session()
        user_id = derive_user_id_from_key(key, app.config.identity_secret)
        
        session.user_id = user_id
        session.auth_method = "key"
        session.authenticated_at = datetime.utcnow()
        
        return format_success_response(
            {
                "status": "connected",
                "user_id": user_id,
            },
            message="Connected to your memory bank via key!"
        )

    @mcp.tool()
    async def check_connection() -> Dict[str, Any]:
        """Check your current connection status and user info."""
        session = _get_session()
        if not session.is_authenticated:
            return format_success_response(
                {"status": "not_connected"},
                message="You are not connected. Use connect_account or connect_with_key."
            )
        
        return format_success_response({
            "status": "connected",
            "user_id": session.user_id,
            "email": session.email,
            "auth_method": session.auth_method,
            "connected_since": str(session.authenticated_at)
        })

    @mcp.tool()
    async def disconnect() -> Dict[str, Any]:
        """Disconnect from your memory bank for this session."""
        session = _get_session()
        session.user_id = None
        session.email = None
        session.auth_method = None
        session.authenticated_at = None
        
        return format_success_response(message="Disconnected successfully.")

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
        # SECURITY HARDENING: Prevent runtime reconfiguration in production
        # If already initialized, return current config (read-only mode)
        if app.is_ready():
            return format_success_response({
                "status": "already_initialized",
                "message": "Memory Bank is already configured. No changes made.",
                "agent_engine_name": app.agent_engine.api_resource.name,
                "project_id": app.config.project_id,
                "location": app.config.location,
                "note": "To change configuration, update AGENT_ENGINE_NAME env var and redeploy."
            })

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
        key: Optional[str] = None,
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate memories from a conversation.

        Analyzes conversation and extracts relevant information to remember.

        Args:
            conversation: List of messages with 'role' and 'content'
            key: Your key for authentication (use same across all AI assistants)
            wait_for_completion: Whether to wait for generation to complete

        Returns:
            Generated memories and operation status
        """
        user_id, error = _get_user_id(key)
        if error:
            return format_error_response(error)
        
        scope = {"user_id": user_id}

        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

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
        key: Optional[str] = None, search_query: Optional[str] = None, top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve memories for the connected user, with optional similarity search.

        Args:
            key: Your key for authentication (use same across all AI assistants)
            search_query: Optional search query for similarity matching
            top_k: Number of results to return (default: 5)

        Returns:
            List of memories with optional similarity scores
        """
        user_id, error = _get_user_id(key)
        if error:
            return format_error_response(error)
        
        scope = {"user_id": user_id}

        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

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

    @mcp.tool()
    async def search_memories(
        search_query: str, key: Optional[str] = None, top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Explicit search tool for memories (Deep Research compatibility).

        Args:
            search_query: Query string for similarity search
            key: Your key for authentication (use same across all AI assistants)
            top_k: Max results

        Returns:
            Memories with similarity scores.
        """
        return await retrieve_memories(key=key, search_query=search_query, top_k=top_k)

    @mcp.tool()
    async def fetch_memory(memory_name: str, key: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch a single memory by resource name.
        
        Args:
            memory_name: Full resource name of the memory
            key: Your key for authentication (use same across all AI assistants)
        """
        user_id, error = _get_user_id(key)
        if error:
            return format_error_response(error)

        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        try:
            memory = app.client.agent_engines.get_memory(name=memory_name)
            
            # Security: Verify scope matches connected user
            memory_scope = getattr(memory, "scope", {})
            if isinstance(memory_scope, dict) and memory_scope.get("user_id") != user_id:
                return format_error_response("Unauthorized: This memory does not belong to you.")

            return format_success_response({"memory": format_memory(memory)})
        except Exception as e:
            logger.error(f"Failed to fetch memory: {e}")
            return format_error_response(str(e))

    # ========================================================================
    # Memory Management Tools
    # ========================================================================

    @mcp.tool()
    async def create_memory(
        fact: str, key: Optional[str] = None, ttl_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a memory directly.

        Args:
            fact: The information to remember
            key: Your key for authentication (use same across all AI assistants)
            ttl_seconds: Optional time-to-live in seconds

        Returns:
            Created memory details
        """
        user_id, error = _get_user_id(key)
        if error:
            return format_error_response(error)
        
        scope = {"user_id": user_id}

        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        # Validate inputs
        if error := validate_memory_fact(fact):
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
    async def delete_memory(memory_name: str, key: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a specific memory by name.

        Args:
            memory_name: Full memory resource name
            key: Your key for authentication (use same across all AI assistants)

        Returns:
            Deletion confirmation
        """
        user_id, error = _get_user_id(key)
        if error:
            return format_error_response(error)

        if not app.is_ready():
            return format_error_response(
                "Memory Bank not initialized. Call initialize_memory_bank first."
            )

        try:
            # First fetch to verify ownership
            memory = app.client.agent_engines.get_memory(name=memory_name)
            memory_scope = getattr(memory, "scope", {})
            if isinstance(memory_scope, dict) and memory_scope.get("user_id") != user_id:
                return format_error_response("Unauthorized: You cannot delete a memory that does not belong to you.")

            app.client.agent_engines.delete_memory(name=memory_name)
            logger.info(f"Deleted memory: {memory_name} for user {user_id}")

            return format_success_response({"deleted": memory_name})
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return format_error_response(str(e))

    @mcp.tool()
    async def list_memories(key: Optional[str] = None, page_size: int = 50) -> Dict[str, Any]:
        """
        List all memories for the connected user.

        Args:
            key: Your key for authentication (use same across all AI assistants)
            page_size: Number of memories to return (default: 50)

        Returns:
            List of memories
        """
        # For Tier 1 isolation, we use retrieve_memories with scope instead of 
        # the global list_memories call to ensure the user only sees their own data.
        return await retrieve_memories(key=key, top_k=page_size)
