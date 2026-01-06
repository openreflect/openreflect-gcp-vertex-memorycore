#!/usr/bin/env python3
"""
Test script for HTTP streamable transport endpoint.

This tests the /mcp endpoint to ensure it properly handles JSON-RPC messages
in a simple request/response pattern (vs SSE).
"""

import asyncio
import json
import sys
from typing import Dict, Any

import httpx


async def test_http_streamable(base_url: str = "http://localhost:8080"):
    """Test the HTTP streamable transport endpoint."""

    print(f"Testing HTTP streamable transport at {base_url}/mcp\n")

    async with httpx.AsyncClient() as client:
        # Test 1: Initialize
        print("1. Testing initialize...")
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }

        response = await client.post(
            f"{base_url}/mcp",
            json=init_request,
            headers={"Content-Type": "application/json"}
        )

        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}\n")

        if response.status_code != 200:
            print("❌ Initialize failed")
            return False

        # Test 2: List tools
        print("2. Testing tools/list...")
        tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        }

        response = await client.post(
            f"{base_url}/mcp",
            json=tools_request,
            headers={"Content-Type": "application/json"}
        )

        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Found {len(result.get('result', {}).get('tools', []))} tools")

        if result.get('result', {}).get('tools'):
            print("Tools:")
            for tool in result['result']['tools'][:3]:  # Show first 3
                print(f"  - {tool.get('name')}: {tool.get('description', '')[:60]}...")
        print()

        if response.status_code != 200:
            print("❌ Tools list failed")
            return False

        # Test 3: List prompts
        print("3. Testing prompts/list...")
        prompts_request = {
            "jsonrpc": "2.0",
            "method": "prompts/list",
            "params": {},
            "id": 3
        }

        response = await client.post(
            f"{base_url}/mcp",
            json=prompts_request,
            headers={"Content-Type": "application/json"}
        )

        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Found {len(result.get('result', {}).get('prompts', []))} prompts\n")

        if response.status_code != 200:
            print("❌ Prompts list failed")
            return False

        # Test 4: Health check (standard endpoint, not MCP)
        print("4. Testing /health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}\n")

        print("✅ All HTTP streamable transport tests passed!")
        return True


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"

    try:
        success = asyncio.run(test_http_streamable(base_url))
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
