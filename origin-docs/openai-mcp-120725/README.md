# OpenAI MCP Documentation

This directory contains OpenAI's Model Context Protocol (MCP) documentation compiled from https://platform.openai.com/docs/guides/tools-connectors-mcp and related pages, optimized for AI retrieval.

## Files

- `connectors-and-mcp-servers.md` - Main guide on using connectors and remote MCP servers with the Responses API
- `building-mcp-servers.md` - Guide on building MCP servers for ChatGPT and API integrations
- `developer-mode.md` - ChatGPT Developer mode documentation
- `openai-mcp-documentation.json` - Complete documentation in structured JSON format (to be created)
- `test-documentation.js` - Test file to validate documentation structure

## Structure

The documentation covers:

1. **Connectors and MCP Servers** - Using OpenAI-maintained connectors and remote MCP servers
2. **Building MCP Servers** - How to build custom MCP servers for ChatGPT and API integrations
3. **Developer Mode** - Full MCP client access in ChatGPT
4. **API Reference** - Responses API documentation for MCP tools

## Key Topics

### Transport Protocols
- Streamable HTTP
- HTTP/SSE (Server-Sent Events)

### Required Tools for ChatGPT/Deep Research
- `search` - Search for documents/results
- `fetch` - Retrieve full document content

### Authentication
- OAuth access tokens
- Dynamic client registration

### Available Connectors
- Dropbox, Gmail, Google Calendar, Google Drive
- Microsoft Teams, Outlook Calendar, Outlook Email
- SharePoint

### Safety and Security
- Prompt injection risks
- Approval workflows
- Data residency considerations

## Testing

Run the test file to validate documentation structure:

```bash
node test-documentation.js
```

## Usage

This documentation is optimized for:
- AI/LLM context retrieval
- Programmatic access
- Search and filtering
- Implementation reference

## Source

Documentation pulled from:
- https://platform.openai.com/docs/guides/tools-connectors-mcp
- https://platform.openai.com/docs/mcp
- https://platform.openai.com/docs/guides/developer-mode
- https://platform.openai.com/docs/api-reference/responses
