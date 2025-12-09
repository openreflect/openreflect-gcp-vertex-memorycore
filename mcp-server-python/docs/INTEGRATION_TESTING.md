# Integration Testing Guide for Vertex AI Memory Bank MCP Server

This guide covers end-to-end testing of the MCP server deployed on Cloud Run.

## Prerequisites

- Cloud Run service deployed and accessible
- Service URL obtained from deployment
- MCP client library installed (Python or JavaScript)
- Google Cloud credentials configured

## Test Service Health

### 1. Health Check

```bash
SERVICE_URL="https://vertex-memory-bank-mcp-xxxxx-uc.a.run.app"

# Test health endpoint
curl ${SERVICE_URL}/health

# Expected response:
# {"status":"healthy","initialized":true}
# OR
# {"status":"initializing","initialized":false} (if not yet initialized)
```

### 2. Root Endpoint

```bash
curl ${SERVICE_URL}/

# Expected response:
# {
#   "service": "Vertex AI Memory Bank MCP Server",
#   "status": "running",
#   "endpoints": {
#     "health": "/health",
#     "sse": "/sse",
#     "message": "/message"
#   }
# }
```

## Test MCP Protocol

### Python Client Test

Create `test_integration.py`:

```python
#!/usr/bin/env python3
"""Integration test for Cloud Run MCP server."""

import asyncio
import json
import os
import sys

import httpx


async def test_initialize(base_url: str):
    """Test MCP initialize method."""
    print("Testing initialize...")
    async with httpx.AsyncClient() as client:
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "integration-test",
                    "version": "1.0"
                }
            }
        }
        response = await client.post(
            f"{base_url}/message",
            json=message,
            timeout=30.0
        )
        print(f"  Status: {response.status_code}")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200


async def test_list_tools(base_url: str):
    """Test MCP tools/list method."""
    print("Testing tools/list...")
    async with httpx.AsyncClient() as client:
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        response = await client.post(
            f"{base_url}/message",
            json=message,
            timeout=30.0
        )
        print(f"  Status: {response.status_code}")
        result = response.json()
        print(f"  Tools found: {len(result.get('result', {}).get('tools', []))}")
        return response.status_code == 200


async def test_initialize_memory_bank(base_url: str):
    """Test initialize_memory_bank tool."""
    print("Testing initialize_memory_bank tool...")
    async with httpx.AsyncClient() as client:
        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "initialize_memory_bank",
                "arguments": {
                    "project_id": "directed-asset-479716-f6",
                    "location": "us-central1"
                }
            }
        }
        response = await client.post(
            f"{base_url}/message",
            json=message,
            timeout=60.0  # Longer timeout for initialization
        )
        print(f"  Status: {response.status_code}")
        print(f"  Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200


async def test_generate_memories(base_url: str):
    """Test generate_memories tool."""
    print("Testing generate_memories tool...")
    async with httpx.AsyncClient() as client:
        message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "generate_memories",
                "arguments": {
                    "conversation": "User: I prefer Python over JavaScript. Assistant: Got it, I'll remember that.",
                    "scope": {"user_id": "test-user-123"},
                    "wait_for_completion": True
                }
            }
        }
        response = await client.post(
            f"{base_url}/message",
            json=message,
            timeout=120.0  # Long timeout for memory generation
        )
        print(f"  Status: {response.status_code}")
        result = response.json()
        print(f"  Response: {json.dumps(result, indent=2)}")
        return response.status_code == 200


async def test_retrieve_memories(base_url: str):
    """Test retrieve_memories tool."""
    print("Testing retrieve_memories tool...")
    async with httpx.AsyncClient() as client:
        message = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "retrieve_memories",
                "arguments": {
                    "scope": {"user_id": "test-user-123"},
                    "search_query": "programming preferences",
                    "top_k": 5
                }
            }
        }
        response = await client.post(
            f"{base_url}/message",
            json=message,
            timeout=60.0
        )
        print(f"  Status: {response.status_code}")
        result = response.json()
        print(f"  Memories found: {len(result.get('result', {}).get('memories', []))}")
        return response.status_code == 200


async def main():
    """Run all integration tests."""
    base_url = os.getenv("SERVICE_URL", "http://localhost:8080")
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"Testing MCP server at {base_url}\n")
    
    results = []
    results.append(await test_initialize(base_url))
    print()
    results.append(await test_list_tools(base_url))
    print()
    results.append(await test_initialize_memory_bank(base_url))
    print()
    results.append(await test_generate_memories(base_url))
    print()
    results.append(await test_retrieve_memories(base_url))
    print()
    
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("All integration tests passed!")
        return 0
    else:
        print("Some integration tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

### Run Integration Tests

```bash
# Set service URL
export SERVICE_URL="https://vertex-memory-bank-mcp-xxxxx-uc.a.run.app"

# Run tests
python test_integration.py ${SERVICE_URL}
```

## Test SSE Endpoint

### Using curl

```bash
# Test SSE endpoint
curl -X POST ${SERVICE_URL}/sse \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0"
      }
    }
  }' \
  --no-buffer
```

### Using Python EventSource

```python
import asyncio
import json
import httpx

async def test_sse():
    async with httpx.AsyncClient() as client:
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }
        
        async with client.stream(
            "POST",
            f"{SERVICE_URL}/sse",
            json=message,
            timeout=30.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(f"Received: {data}")

asyncio.run(test_sse())
```

## Test with MCP Client Library

### Python MCP Client

```python
from mcp.client.sse import sse_client
from mcp import ClientSession

async def test_with_mcp_client():
    async with sse_client(
        url=f"{SERVICE_URL}/sse"
    ) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")
            
            # Call tool
            result = await session.call_tool(
                "initialize_memory_bank",
                {
                    "project_id": "directed-asset-479716-f6",
                    "location": "us-central1"
                }
            )
            print(f"Result: {result}")

asyncio.run(test_with_mcp_client())
```

## Test Memory Bank Operations

### Full Workflow Test

```python
async def test_full_workflow():
    """Test complete memory bank workflow."""
    async with httpx.AsyncClient() as client:
        base_url = os.getenv("SERVICE_URL")
        
        # 1. Initialize memory bank
        init_result = await call_tool(
            client, base_url, "initialize_memory_bank",
            {"project_id": "directed-asset-479716-f6", "location": "us-central1"}
        )
        print(f"Initialized: {init_result}")
        
        # 2. Generate memories
        gen_result = await call_tool(
            client, base_url, "generate_memories",
            {
                "conversation": "User: My favorite color is blue. Assistant: I'll remember that.",
                "scope": {"user_id": "test-user"},
                "wait_for_completion": True
            }
        )
        print(f"Generated: {gen_result}")
        
        # 3. Retrieve memories
        retrieve_result = await call_tool(
            client, base_url, "retrieve_memories",
            {
                "scope": {"user_id": "test-user"},
                "search_query": "favorite color",
                "top_k": 5
            }
        )
        print(f"Retrieved: {retrieve_result}")
        
        # Verify round-trip
        memories = retrieve_result.get("result", {}).get("memories", [])
        assert len(memories) > 0, "No memories retrieved"
        print("Round-trip test passed!")

async def call_tool(client, base_url, tool_name, arguments):
    """Helper to call MCP tool."""
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    response = await client.post(f"{base_url}/message", json=message, timeout=120.0)
    return response.json()
```

## Performance Testing

### Load Test

```python
import asyncio
import time
import httpx

async def load_test(base_url: str, num_requests: int = 100):
    """Run load test."""
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        tasks = []
        
        for i in range(num_requests):
            message = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "load-test", "version": "1.0"}
                }
            }
            tasks.append(
                client.post(f"{base_url}/message", json=message, timeout=10.0)
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        successful = sum(1 for r in results if isinstance(r, httpx.Response) and r.status_code == 200)
        failed = num_requests - successful
        duration = end_time - start_time
        
        print(f"Requests: {num_requests}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Duration: {duration:.2f}s")
        print(f"Requests/sec: {num_requests/duration:.2f}")

asyncio.run(load_test("https://vertex-memory-bank-mcp-xxxxx-uc.a.run.app", 100))
```

## Troubleshooting

### Common Issues

1. **Connection Timeout**
   - Check service URL is correct
   - Verify service is running: `gcloud run services describe vertex-memory-bank-mcp`
   - Check firewall rules

2. **Authentication Errors**
   - Verify service account permissions
   - Check IAM bindings
   - Review Cloud Run logs

3. **Memory Bank Errors**
   - Verify Vertex AI API is enabled
   - Check project ID and location
   - Review service account has `aiplatform.user` role

4. **Protocol Errors**
   - Verify JSON-RPC message format
   - Check method names match registered tools
   - Review MCP protocol version compatibility

### Debug Commands

```bash
# Check service status
gcloud run services describe vertex-memory-bank-mcp \
  --region us-central1 \
  --project directed-asset-479716-f6

# View recent logs
gcloud run services logs read vertex-memory-bank-mcp \
  --region us-central1 \
  --project directed-asset-479716-f6 \
  --limit 50

# Test health endpoint
curl -v https://vertex-memory-bank-mcp-xxxxx-uc.a.run.app/health
```

## Test Checklist

- [ ] Health endpoint returns 200 OK
- [ ] Root endpoint returns service info
- [ ] Initialize method works
- [ ] Tools/list returns available tools
- [ ] initialize_memory_bank tool works
- [ ] generate_memories tool works
- [ ] retrieve_memories tool works
- [ ] Round-trip test (write then read) succeeds
- [ ] SSE endpoint streams responses
- [ ] Error handling works correctly
- [ ] Performance meets requirements (< 2s P95 latency)

## Next Steps

After successful integration testing:

1. Set up monitoring (see MONITORING.md)
2. Configure alerts (see MONITORING.md)
3. Review security (see SECURITY.md)
4. Document any issues found
5. Plan production deployment
