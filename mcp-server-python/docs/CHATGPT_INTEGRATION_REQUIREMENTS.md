# ChatGPT Web Interface Integration Requirements

*Last Updated: 2025-12-21 21:36:53 UTC*

## Overview

To functionally test your MCP server with the ChatGPT web interface, you need to meet specific requirements and follow OpenAI's integration guidelines. This document summarizes the requirements based on the latest OpenAI documentation.

## Documentation URLs Visited

1. **Build MCP Server Guide**
   - URL: https://developers.openai.com/apps-sdk/build/mcp-server/
   - Purpose: Complete guide on building MCP servers for ChatGPT Apps

2. **MCP Server Integration Guide**
   - URL: https://platform.openai.com/docs/mcp
   - Purpose: Building MCP servers for ChatGPT connectors, deep research, and API integrations

3. **Testing Integration Guide**
   - URL: https://developers.openai.com/apps-sdk/deploy/testing/
   - Purpose: Testing strategies and validation steps for MCP server integration

## Requirements for ChatGPT Web Interface Testing

### 1. HTTPS Endpoint (Required)

- **Requirement**: Your MCP server MUST be accessible over HTTPS
- **Development**: Use a tunneling service like ngrok to expose localhost:
  ```bash
  ngrok http <port>
  # Example: ngrok http 8080
  # Result: https://<subdomain>.ngrok.app -> http://127.0.0.1:8080
  ```
- **Production**: Deploy to a low-latency HTTPS host (Cloudflare Workers, Fly.io, Vercel, AWS, Google Cloud Run, etc.)
- **SSE Endpoint**: The URL must end with `/sse/` for Server-Sent Events transport
  - Example: `https://your-server.com/sse/`

### 2. MCP Protocol Implementation

Your server must implement the Model Context Protocol (MCP) with:

- **JSON-RPC 2.0** protocol support
- **SSE (Server-Sent Events)** transport for streaming
- **Tool definitions** that conform to MCP specification
- **Proper content array responses** for tool results

### 3. Developer Mode Access

- **Requirement**: ChatGPT Pro and Plus users can enable Developer Mode
- **Location**: Settings → Connectors → Advanced → Developer mode
- **Purpose**: Access to complete set of MCP tools and custom connector configuration

### 4. Server Configuration

#### Required Endpoints

1. **SSE Endpoint**: `/sse` or `/sse/`
   - Must support GET and POST requests
   - Returns Server-Sent Events stream
   - First event should be `event: endpoint` with message endpoint URL

2. **Message Endpoint**: `/message` (or as specified in SSE endpoint event)
   - Handles JSON-RPC 2.0 messages
   - Supports `initialize`, `tools/list`, `tools/call`, etc.

3. **Health Check** (Recommended): `/health`
   - Returns server status and readiness

#### MCP Protocol Methods

Your server must handle:
- `initialize` - Protocol handshake
- `tools/list` - Return available tools
- `tools/call` - Execute tool with arguments
- `prompts/list` - Return available prompts (optional)
- `prompts/get` - Get prompt content (optional)

### 5. Authentication (Optional but Recommended)

- **Bearer Token**: Can be configured via `CONNECTOR_BEARER_TOKEN` environment variable
- **OAuth**: Recommended for production using dynamic client registration
- **Service Account**: For GCP deployments (already implemented)

### 6. Testing Tools

#### MCP Inspector (Local Development)

```bash
npx @modelcontextprotocol/inspector@latest
```

- Enter server URL: `http://127.0.0.1:8080/sse` (or your local endpoint)
- Use to list tools and call them
- Inspects raw requests and responses
- Renders components inline

#### ChatGPT Developer Mode

1. Navigate to: **Settings → Connectors → Developer mode**
2. Click **Create** or **Add Connector**
3. Provide:
   - **Name**: Your connector name
   - **MCP Server URL**: `https://your-server.com/sse/`
   - **Authentication**: Bearer token (if configured)
4. Toggle connector on in a new conversation
5. Test with various prompts

#### API Playground (Alternative Testing)

1. Go to: https://platform.openai.com/playground
2. Choose **Tools → Add → MCP Server**
3. Provide HTTPS endpoint
4. Connect and test
5. Inspect JSON request/response pairs

### 7. Tool Response Format

Tool responses must return content arrays:

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"result\": \"data\"}"
    }
  ]
}
```

For structured data, encode JSON as a string in the `text` field.

### 8. Current Implementation Status

Based on codebase analysis:

✅ **Implemented:**
- SSE endpoint (`/sse`)
- Message endpoint (`/message`)
- JSON-RPC 2.0 protocol support
- Health check endpoint (`/health`)
- Bearer token authentication (optional)
- All required MCP tools (initialize_memory_bank, generate_memories, etc.)

⚠️ **Needs Verification:**
- SSE endpoint format (must return `event: endpoint` first)
- Message endpoint URL construction in SSE response
- HTTPS deployment configuration
- CORS headers for ChatGPT web interface

### 9. Testing Checklist

Before testing with ChatGPT web interface:

- [ ] Server deployed to HTTPS endpoint
- [ ] SSE endpoint accessible at `https://your-server.com/sse/`
- [ ] Message endpoint responds to JSON-RPC requests
- [ ] Health check returns 200 OK
- [ ] Tools list returns all available tools
- [ ] Tool calls execute successfully
- [ ] Bearer token authentication works (if configured)
- [ ] CORS headers allow ChatGPT origin
- [ ] Tested with MCP Inspector locally
- [ ] Developer Mode enabled in ChatGPT settings

### 10. Connection Steps in ChatGPT

1. **Enable Developer Mode**:
   - Go to ChatGPT Settings
   - Navigate to Connectors → Advanced
   - Enable "Developer mode"

2. **Add Connector**:
   - In Connectors tab, click "Create"
   - Fill in connector details:
     - Name: "OpenReflect" (or your preferred name)
     - MCP Server URL: `https://your-service.a.run.app/sse`
     - Authentication: Bearer token (if using `CONNECTOR_BEARER_TOKEN`)

3. **Test Connection**:
   - Toggle connector on in a new conversation
   - Try prompts like:
     - "Initialize the memory bank"
     - "Remember that I prefer Python"
     - "What memories do you have about me?"

### 11. Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| Connection refused | Ensure server is accessible over HTTPS |
| SSE endpoint not found | Verify URL ends with `/sse/` |
| Authentication failed | Check bearer token configuration |
| CORS errors | Add ChatGPT origin to CORS allowlist |
| Tools not appearing | Verify `tools/list` returns correct format |
| Tool calls failing | Check JSON-RPC response format |

### 12. Security Considerations

- **Never expose API keys** in tool responses or metadata
- **Validate all inputs** before processing
- **Use HTTPS** for all connections
- **Implement rate limiting** for production
- **Review authentication flows** before deployment
- **Monitor logs** for suspicious activity

## Next Steps

1. Deploy your MCP server to Cloud Run with HTTPS
2. Verify SSE endpoint is accessible
3. Test with MCP Inspector locally
4. Configure connector in ChatGPT Developer Mode
5. Run functional tests with various prompts
6. Monitor logs and performance

## Additional Resources

- [MCP Specification](https://modelcontextprotocol.io/)
- [OpenAI Apps SDK Documentation](https://developers.openai.com/apps-sdk)
- [MCP Inspector Tool](https://modelcontextprotocol.io/docs/tools/inspector)
- [Developer Mode Guide](https://platform.openai.com/docs/guides/developer-mode)

