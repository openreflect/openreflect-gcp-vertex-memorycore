# openreflect-core-SD-MB-v0.1-112925

This repository contains the Model Context Protocol (MCP) server for Vertex AI Memory Bank.

## Project Structure

- **`mcp-server-python/`**: The **production-ready** Python implementation.
  - Contains the Dockerfile, Cloud Run provisioning scripts, and source code.
  - This is the version being deployed to Google Cloud Run.
  
- **`mcp-server-ghost-js/`**: A Node.js prototype client.
  - Useful for reference or future JS-based iterations.
  
- **`docs/`**: Project documentation and reference specs.

- **`secrets/`**: Local configuration secrets (git-ignored).

## Getting Started

To deploy the main server, navigate to `mcp-server-python/` and follow the `DEPLOYMENT.md` guide.
