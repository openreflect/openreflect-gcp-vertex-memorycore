<mark style="background-color: #e1e100">_This is a personal project by Ivan Nardini to explore how to build a Model Context Protocol (MCP) server for Vertex AI Memory Bank._</mark>

<mark style="background-color: #e1e100">_Vertex AI Memory Bank MCP server is not a Google product. And it is not officially support._</mark>

---

# Vertex AI Memory Bank MCP Server

A simple MCP (Model Context Protocol) server that enables LLMs to generate and retrieve long-term memories using Vertex AI's Memory Bank.

## Why This Project?

This server demonstrates how to build an MCP server with Vertex AI Memory Bank. It has been inspired by a developer request and released for developers.

## Prerequisites

- Python 3.11 or higher
- Google Cloud account with Vertex AI API enabled
- Basic understanding of async Python (helpful but not required)

## Quick Start

### Setup Google Cloud

```bash
# Install gcloud CLI (if not already installed)
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com
```

### Install

```bash
# Clone the repository
git clone https://github.com/yourusername/vertex-ai-memory-bank-mcp.git
cd vertex-ai-memory-bank-mcp

# Install with pip
pip install -r requirements.txt

# OR install with uv (faster, recommended)
uv sync

# For running examples (optional)
pip install -e ".[examples]"
# OR with uv
uv sync --extra examples
```

### Configure

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your project details
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

### Run Your First Example

**Interactive Tutorial (Recommended):** Open `get_started_with_memory_bank_mcp.ipynb` in Jupyter

**Or try the command-line examples:**

```bash
# Basic MCP Client Usage
python examples/basic_usage.py

# Gemini Agent with Memory
python examples/gemini_memory_agent.py

# Automatic Tool Calling with Gemini
python examples/automatic_tool_calling.py
```

## Use with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "memory-bank": {
      "command": "python",
      "args": ["/path/to/memory_bank_server.py"],
      "env": {
        "GOOGLE_CLOUD_PROJECT": "your-project-id",
        "GOOGLE_CLOUD_LOCATION": "us-central1"
      }
    }
  }
}
```

## Key Concepts

### Memory Scope

Memories are scoped to users or contexts:

```python
scope = {"user_id": "alice123"}
```

### Memory Topics

Categorize what to remember:

```python
topics = ["USER_PREFERENCES", "USER_PERSONAL_INFO"]
```

### Semantic Search

Find relevant memories with similarity search:

```python
search_query = "programming preferences"
top_k = 5
```

## Available Tools

| Tool                     | Purpose                             | Example Use Case       |
| ------------------------ | ----------------------------------- | ---------------------- |
| `initialize_memory_bank` | Set up connection to Vertex AI      | First-time setup       |
| `generate_memories`      | Extract memories from conversations | After chat sessions    |
| `retrieve_memories`      | Fetch relevant memories             | Personalize responses  |
| `create_memory`          | Manually add a memory               | Store user preferences |
| `delete_memory`          | Remove specific memory              | User requests deletion |
| `list_memories`          | View all stored memories            | Debugging/inspection   |

## Common Patterns

### Pattern 1: Conversation Memory

```python
# After each conversation turn
await session.call_tool(
    "generate_memories",
    {
        "conversation": conversation_history,
        "scope": {"user_id": user_id},
        "wait_for_completion": True
    }
)
```

### Pattern 2: Explicit Memory

```python
# Store specific facts
await session.call_tool(
    "create_memory",
    {
        "fact": "User prefers dark mode",
        "scope": {"user_id": user_id}
    }
)
```

### Pattern 3: Context Retrieval

```python
# Get relevant context before responding
memories = await session.call_tool(
    "retrieve_memories",
    {
        "scope": {"user_id": user_id},
        "search_query": user_message,
        "top_k": 5
    }
)
```

## Project Structure

```text
vertex-ai-memory-bank-mcp/
├── memory_bank_server.py                     # Main entry point
├── src/                                       # Modular source code
│   ├── __init__.py
│   ├── server.py                             # Server orchestration
│   ├── tools.py                              # MCP tool implementations
│   ├── config.py                             # Configuration management
│   ├── app_state.py                          # Application state
│   ├── validators.py                         # Input validation
│   └── formatters.py                         # Data formatting
├── examples/                                 # Usage examples
│   ├── basic_usage.py                        # Basic MCP client usage
│   ├── automatic_tool_calling.py             # Automatic function calling
│   └── claude_config.json                    # Claude Desktop config
├── get_started_with_memory_bank_mcp.ipynb    # Getting started tutorial
├── pyproject.toml                            # Project config (pip & uv)
├── requirements.txt                          # Dependencies (pip)
├── uv.lock                                   # Lock file (uv)
├── .env.example                              # Environment template
├── .gitignore                                # Git ignore rules
├── .python-version                           # Python version
├── README.md                                 # This file
└── LICENSE                                   # Apache 2.0 License
```

## Troubleshooting

### "Connection closed" error

**Solution**: Check that your MCP server is using stderr for logging, not stdout.

### "Not authenticated"

**Solution**: Run `gcloud auth application-default login`

## Contributing

This project is meant to inspire. Feel free to fork and create your own version as well as share your production implementations.

## Resources

- [Interactive Tutorial](get_started_with_memory_bank_mcp.ipynb) - Start here!
- [Model Context Protocol Docs](https://modelcontextprotocol.io/)
- [Vertex AI Memory Bank](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/overview)
- [MCP Server Examples](https://github.com/modelcontextprotocol/servers)

## License

This project is licensed under the Apache 2.0 License.

---
