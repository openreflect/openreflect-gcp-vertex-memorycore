"""MCP Prompts - Pre-built prompts for common memory patterns."""

from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP):
    """Register all MCP prompts with the server."""
    
    @mcp.prompt()
    async def memory_extraction_prompt(conversation: str) -> str:
        """
        Prompt for extracting memories from a conversation.
        
        Args:
            conversation: The conversation text to analyze
        
        Returns:
            A prompt for memory extraction
        """
        return f"""Analyze this conversation and extract key information to remember:

{conversation}

Extract the following types of information:
1. Personal information (names, relationships, preferences)
2. Important facts mentioned
3. Decisions or commitments made
4. Anything explicitly asked to remember

Format each memory as a clear, standalone fact that can be understood without context.
Be specific and include relevant details."""
    
    @mcp.prompt()
    async def memory_search_prompt(user_query: str) -> str:
        """
        Convert a user question into an optimized memory search query.
        
        Args:
            user_query: The user's question
        
        Returns:
            Optimized search query
        """
        return f"""Convert this question into keywords for searching memories:

Question: {user_query}

Extract the key concepts, entities, and topics that would match relevant memories.
Focus on:
- Nouns and proper names
- Specific terms and concepts
- Important descriptors
- Action words if relevant

Return a concise search query optimized for similarity matching."""
    
    @mcp.prompt()
    async def memory_consolidation_prompt(existing_memories: str, new_fact: str) -> str:
        """
        Prompt for consolidating or merging related memories.
        
        Args:
            existing_memories: Current memories as text
            new_fact: New fact to potentially consolidate
        
        Returns:
            Prompt for memory consolidation
        """
        return f"""Review these existing memories and determine how to handle a new fact:

Existing memories:
{existing_memories}

New fact to consider:
{new_fact}

Determine if the new fact:
1. Is completely new and should be added as a separate memory
2. Updates or enhances an existing memory (specify which one and how to merge)
3. Contradicts an existing memory (specify which one should be kept)
4. Is redundant and should not be stored

Provide your recommendation with clear reasoning."""