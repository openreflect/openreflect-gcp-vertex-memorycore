# Streamable HTTP Transport

MemoryCore supports a modern Streamable HTTP MCP endpoint at:

```text
/mcp
```

This is the current remote MCP transport shape. It uses one HTTP endpoint for
client-to-server JSON-RPC messages, instead of the older two-endpoint
HTTP+SSE pattern.

## Supported Transports

MemoryCore currently exposes three MCP access paths:

```text
stdio              local MCP process transport
/mcp              Streamable HTTP transport for remote clients
/sse + /message   legacy HTTP+SSE transport for older clients
```

The legacy endpoints remain available for compatibility. New remote integrations
should prefer `/mcp` when the client supports Streamable HTTP.

## Client Handoff Pattern

Streamable HTTP is useful when several MCP-capable clients need to use the same
remote memory service. A deployment can expose one authenticated `/mcp` endpoint
and let each client identify itself during `initialize`.

Example flow:

1. A local coding assistant initializes against `https://SERVICE_URL/mcp` and
   writes memories while working through an implementation.
2. A desktop assistant initializes against the same endpoint later and retrieves
   relevant memories using the same scope.
3. A browser-based MCP client initializes against the same endpoint and can
   continue the workflow without copying local files between clients.

The server sees these as separate MCP client sessions using a shared backend
memory store. Provenance-aware deployments can use the client name, protocol
version, transport, scope, and tool calls as inputs to their private provenance
layer.

Suggested `clientInfo.name` values:

```text
chatgpt-web
claude-desktop
gemini-cli
goose
local-dev-agent
```

These names are examples only. Use stable names that make sense for the client
or workflow being connected.

## Basic Initialize Request

```bash
curl -i https://SERVICE_URL/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2025-03-26" \
  -H "Authorization: Bearer YOUR_CONNECTOR_BEARER_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {
        "name": "example-client",
        "version": "1.0"
      }
    }
  }'
```

Expected response headers include:

```text
MCP-Protocol-Version: 2025-03-26
Mcp-Session-Id: <server-generated-session-id>
```

Use the returned `Mcp-Session-Id` header on follow-up requests when the client
supports MCP session lifecycle behavior.

## Calling Tools

After initialization, send `tools/list` or `tools/call` to the same endpoint:

```bash
curl -i https://SERVICE_URL/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "MCP-Protocol-Version: 2025-03-26" \
  -H "Mcp-Session-Id: SESSION_ID_FROM_INITIALIZE" \
  -H "Authorization: Bearer YOUR_CONNECTOR_BEARER_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

## Optional GET Stream

Clients that open `GET /mcp` with a valid `Mcp-Session-Id` receive an SSE stream
with keepalives. The current server does not emit server-initiated tool
notifications, but the endpoint is present for clients that expect the
Streamable HTTP GET shape.

## Session Termination

Clients may terminate a session with:

```bash
curl -i -X DELETE https://SERVICE_URL/mcp \
  -H "Mcp-Session-Id: SESSION_ID_FROM_INITIALIZE" \
  -H "Authorization: Bearer YOUR_CONNECTOR_BEARER_TOKEN"
```

## Compatibility Note

Streamable HTTP may still use Server-Sent Events internally for streaming. The
important protocol change is that modern remote MCP uses a single MCP endpoint
such as `/mcp`, while legacy HTTP+SSE uses separate `/sse` and `/message`
endpoints.
