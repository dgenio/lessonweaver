# Model Context Protocol integration

lessonweaver ships an optional stdio MCP server so agent runtimes can propose
new lesson candidates and load already reviewed skills from the same registry
the CLI uses. The server never exposes approval or promotion actions: humans
must still use the review CLI before a candidate can become trusted guidance.

## Install

The base package remains dependency-free. Install the MCP server only when an
MCP client will run it:

```bash
pip install "lessonweaver[mcp]"
```

For local development:

```bash
pip install -e ".[mcp]"
```

## Run

```bash
lessonweaver-mcp --registry-root ~/.lessonweaver/registry
```

Omit `--registry-root` to use the default CLI registry at
`~/.lessonweaver/registry`.

## Claude Code example

Add a stdio server entry that points to the installed command:

```json
{
  "mcpServers": {
    "lessonweaver": {
      "command": "lessonweaver-mcp",
      "args": ["--registry-root", "/Users/you/.lessonweaver/registry"]
    }
  }
}
```

## Tools

| Tool | Purpose |
| --- | --- |
| `submit_trace(trace_json)` | Validates and sanitizes a trace, runs detection, and saves resulting candidates. |
| `list_pending_candidates()` | Lists candidates that still need human review. |
| `get_candidate(candidate_id)` | Returns one saved candidate plus review guidance. |
| `load_skills(task, agent_type, tools, budget_chars, ...)` | Returns the same compiled context as `SkillLoader.load_for_task`. |
| `explain_load(task, ...)` | Returns load diagnostics with skipped reasons, budget usage, overlaps, and snippet. |

The server intentionally does not register `answer`, `approve`, or
`promote-skill`. Agent-submitted traces are untrusted input; the server applies
the default `TraceSanitizer` before detection, and review remains the boundary
where a human decides whether a candidate is reusable guidance.
