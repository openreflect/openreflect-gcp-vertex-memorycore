#!/usr/bin/env python3
"""Test script for HTTP server endpoints."""

import asyncio
import json
import sys
from typing import Dict, Any

import httpx


async def test_health_endpoint(base_url: str) -> bool:
    """Test the health endpoint."""
    print("Testing /health endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health", timeout=5.0)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.json()}")
            return response.status_code in [200, 503]  # 503 is OK if not initialized
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def test_root_endpoint(base_url: str) -> bool:
    """Test the root endpoint."""
    print("Testing / endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/", timeout=5.0)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def test_message_endpoint(base_url: str) -> bool:
    """Test the /message endpoint with initialize request."""
    print("Testing /message endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-12-01",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0"
                    }
                }
            }
            response = await client.post(
                f"{base_url}/message",
                json=message,
                timeout=10.0
            )
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text}")
            return response.status_code == 200
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def test_streamable_http_endpoint(base_url: str) -> bool:
    """Test the /mcp Streamable HTTP endpoint."""
    print("Testing /mcp Streamable HTTP endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-streamable-client",
                        "version": "1.0",
                    },
                },
            }
            response = await client.post(
                f"{base_url}/mcp",
                json=message,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2025-03-26",
                },
                timeout=10.0,
            )
            print(f"  Status: {response.status_code}")
            print(f"  MCP-Protocol-Version: {response.headers.get('mcp-protocol-version')}")
            print(f"  Mcp-Session-Id: {response.headers.get('mcp-session-id')}")
            print(f"  Response: {response.text}")
            data = response.json()
            return bool(
                response.status_code == 200
                and response.headers.get("mcp-session-id") is not None
                and data.get("result", {}).get("serverInfo", {}).get("name")
            )
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def test_sse_endpoint(base_url: str) -> bool:
    """Test the /sse endpoint."""
    print("Testing /sse endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            # Simulate Cloud Run / reverse proxy headers so the SSE endpoint
            # advertises an https:// message endpoint.
            headers = {
                "X-Forwarded-Proto": "https",
                "Host": "example.test",
            }
            async with client.stream(
                "GET",
                f"{base_url}/sse",
                headers=headers,
                timeout=10.0
            ) as response:
                print(f"  Status: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('content-type')}")
                async for line in response.aiter_lines():
                    if line.startswith("event: endpoint"):
                        continue
                    if line.startswith("data: "):
                        endpoint_url = line[6:].strip()
                        print(f"  SSE Endpoint URL: {endpoint_url}")
                        return endpoint_url.startswith("https://example.test/message")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            return False


async def main():
    """Run all tests."""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    print(f"Testing HTTP server at {base_url}\n")
    
    results = []
    results.append(await test_health_endpoint(base_url))
    print()
    results.append(await test_root_endpoint(base_url))
    print()
    results.append(await test_message_endpoint(base_url))
    print()
    results.append(await test_streamable_http_endpoint(base_url))
    print()
    results.append(await test_sse_endpoint(base_url))
    print()
    
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
