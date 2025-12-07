#!/usr/bin/env python3
"""
Basic usage example for Vertex AI Memory Bank MCP Server

This example demonstrates how to use the Memory Bank MCP client
to generate and retrieve memories.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MemoryBankMCPClient:
    """A client for interacting with the Memory Bank MCP server."""

    def __init__(self, server_path: str, project_id: str, location: str):
        """Initialize the Memory Bank MCP client."""
        self.project_id = project_id
        self.location = location
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_path],
            env={
                "GOOGLE_CLOUD_PROJECT": self.project_id,
                "GOOGLE_CLOUD_LOCATION": self.location
            }
        )
        self.session = None
        self.initialized = False
        self.stdio_cm = None
        self.session_cm = None

    async def connect(self):
        """Establish connection to the MCP server."""
        self.stdio_cm = stdio_client(self.server_params)
        self.read, self.write = await self.stdio_cm.__aenter__()

        self.session_cm = ClientSession(self.read, self.write)
        self.session = await self.session_cm.__aenter__()

        await self.session.initialize()
        print("Connected to Memory Bank MCP server")

        return self

    async def disconnect(self):
        """Close the connection to the MCP server."""
        if self.session_cm:
            await self.session_cm.__aexit__(None, None, None)
        if self.stdio_cm:
            await self.stdio_cm.__aexit__(None, None, None)
        print("\nDisconnected from Memory Bank MCP server")

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Call a tool on the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        result = await self.session.call_tool(tool_name, arguments)

        if hasattr(result, 'content') and result.content:
            if result.content[0].type == 'text':
                return json.loads(result.content[0].text)

        return result

    async def initialize_memory_bank(self, memory_topics: List[str] = None):
        """Initialize the Memory Bank."""
        if not self.initialized:
            result = await self.call_tool(
                "initialize_memory_bank",
                {
                    "project_id": self.project_id,
                    "location": self.location,
                    "memory_topics": memory_topics or ["USER_PREFERENCES", "USER_PERSONAL_INFO"]
                }
            )
            self.initialized = True
            return result
        return {"status": "already_initialized"}


async def demo_basic_operations():
    """Demonstrate basic Memory Bank operations via MCP."""

    # Configuration
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    SERVER_PATH = str(Path(__file__).parent.parent / "memory_bank_server.py")

    # Create and connect client
    client = MemoryBankMCPClient(
        server_path=SERVER_PATH,
        project_id=PROJECT_ID,
        location=LOCATION
    )

    try:
        await client.connect()

        # Initialize Memory Bank
        print("\nInitializing Memory Bank...")
        init_result = await client.initialize_memory_bank()
        print(f"Result: {json.dumps(init_result, indent=2)[:200]}...")

        # Generate memories from a conversation
        print("\nGenerating memories from conversation...")
        conversation = [
            {"role": "user", "content": "Hi, I'm Alice. I work as a data scientist in San Francisco."},
            {"role": "assistant", "content": "Nice to meet you, Alice! How can I help you today?"},
            {"role": "user", "content": "I'm interested in learning about machine learning with Python."}
        ]

        gen_result = await client.call_tool(
            "generate_memories",
            {
                "conversation": conversation,
                "scope": {"user_id": "alice_demo_123"},
                "wait_for_completion": True
            }
        )
        print(f"Generated memories: {json.dumps(gen_result, indent=2)[:300]}...")

        # Retrieve memories
        print("\nRetrieving memories...")
        retrieve_result = await client.call_tool(
            "retrieve_memories",
            {
                "scope": {"user_id": "alice_demo_123"},
                "search_query": "programming interests",
                "top_k": 3
            }
        )
        print(f"Retrieved: {json.dumps(retrieve_result, indent=2)[:300]}...")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    # Note: This example requires proper Google Cloud authentication
    # Set up your credentials before running:
    # export GOOGLE_CLOUD_PROJECT="your-project-id"
    # export GOOGLE_CLOUD_LOCATION="us-central1"
    # gcloud auth application-default login

    asyncio.run(demo_basic_operations())
