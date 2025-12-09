# Agent Collaboration Archive

This folder captures insights, decisions, and session summaries from AI-assisted development of the OpenReflect project.

## Purpose

- **Institutional Memory**: Preserve the "why" behind decisions
- **Onboarding**: Help new contributors understand system evolution
- **Multi-Agent Collaboration**: Allow different AI models to read each other's context
- **Debugging**: Trace back to past analysis when issues arise

## Structure

```
agent-collab/
├── README.md                    # This file
├── sessions/                    # Raw session outputs and summaries
│   └── {model}-{role}-{date}-{time}.md
├── decisions/                   # Architecture and design decisions
│   └── {topic}-{date}.md
└── reviews/                     # Security, code, and deployment reviews
    └── {type}-review-{date}.md
```

## Naming Convention

### Session Files
```
{model}-{role}-{date}-{time}.md

Examples:
- opus-45-collaborator-12925-1905.md
- gpt-51-documenter-12925-1905.md
- claude-analyst-121025-0930.md
```

| Component | Description |
|-----------|-------------|
| `model` | AI model identifier (opus-45, gpt-51, claude, etc.) |
| `role` | Session purpose (collaborator, documenter, reviewer, debugger) |
| `date` | MMDDYY format |
| `time` | HHMM 24-hour format |

### Decision Files
```
{topic}-{date}.md

Examples:
- chatgpt-mcp-transport-120925.md
- single-tenant-architecture-120825.md
```

### Review Files
```
{type}-review-{date}.md

Examples:
- security-review-120925.md
- deployment-review-121025.md
```

## Usage

### After an AI Session
1. Capture valuable insights in a session file
2. Move architectural decisions to `decisions/`
3. Move security/review findings to `reviews/`

### Before Starting Work
1. Review recent sessions for context
2. Check `decisions/` for relevant constraints
3. Reference past `reviews/` for known issues

## Relationship to Other Project Artifacts

| Artifact | Purpose | Lifespan |
|----------|---------|----------|
| `agent-collab/` | AI session documentation | Permanent (commit to git) |
| `.cursor/plans/` | Cursor IDE task tracking | Temporary (gitignored) |
| `docs/` | User-facing documentation | Permanent |
| `openreflect-*.md` | High-level status/plans | Working documents |

## Contributing

When adding files:
1. Follow the naming convention
2. Include a date and session context at the top
3. Summarize key findings and recommendations
4. Link to relevant code files when applicable

