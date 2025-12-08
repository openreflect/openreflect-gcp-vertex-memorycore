# MCP Server (Ghost JS)

This directory contains a legacy/prototype Node.js implementation of the Memory Bank client.
It is functional but currently superseded by the Python implementation in `../mcp-server-python`.

## Usage

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run examples:
   ```bash
   node example_search.js
   node example_write.js
   ```

## Note
This project relies on `google-auth-library` and requires valid Google Cloud credentials to be configured in your environment.
