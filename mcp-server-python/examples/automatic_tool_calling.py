#!/usr/bin/env python3
"""
Automatic Tool Calling with Gemini and MCP

This demonstrates Gemini's automatic function calling capability
with Memory Bank MCP tools. Gemini will automatically call the
appropriate Memory Bank tools to fulfill user requests.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def demo_automatic_tool_calling():
    """Demonstrate Gemini's automatic tool calling with Memory Bank."""

    # Configuration
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
    LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    SERVER_PATH = str(Path(__file__).parent.parent / "memory_bank_server.py")

    # Create Gemini client
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    # Create MCP server parameters
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_PATH],
        env={"GOOGLE_CLOUD_PROJECT": PROJECT_ID, "GOOGLE_CLOUD_LOCATION": LOCATION},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize MCP session
            await session.initialize()

            print("Initializing Memory Bank...\n")

            # Initialize Memory Bank first
            init_result = await session.call_tool(
                "initialize_memory_bank",
                {
                    "project_id": PROJECT_ID,
                    "location": LOCATION,
                    "memory_topics": ["USER_PREFERENCES", "USER_PERSONAL_INFO"],
                },
            )

            if hasattr(init_result, "content") and init_result.content:
                init_data = json.loads(init_result.content[0].text)
                engine_name = init_data.get("agent_engine_name")
                print(f"Memory Bank initialized with engine:\n   {engine_name}\n")

            # Turn 1: Store memories
            print("=" * 100)
            print("TURN 1: Storing memories")
            print("=" * 100)

            store_prompt = """
            Please create two memories for me:
            1. I (user_id: "gemini_demo_user") prefer dark mode in all applications
            2. I (user_id: "gemini_demo_user") love Python programming

            Confirm when the memories are stored.
            """

            print("Sending request to Gemini to store memories...\n")

            response1 = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=store_prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    tools=[session],
                ),
            )

            print("Gemini Response:")
            print(response1.text)
            print("\n")

            # Turn 2: Retrieve memories
            print("=" * 100)
            print("TURN 2: Retrieving memories")
            print("=" * 100)

            retrieve_prompt = """
            Now retrieve all memories for user_id: "gemini_demo_user" and show me what you found.
            """

            print("Sending request to Gemini to retrieve memories...\n")

            response2 = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=retrieve_prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    tools=[session],
                ),
            )

            print("Gemini Response:")
            print(response2.text)
            print("=" * 100)


if __name__ == "__main__":
    # Note: This example requires proper Google Cloud authentication
    # Set up your credentials before running:
    # export GOOGLE_CLOUD_PROJECT="your-project-id"
    # export GOOGLE_CLOUD_LOCATION="us-central1"
    # gcloud auth application-default login

    asyncio.run(demo_automatic_tool_calling())
