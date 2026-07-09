# MCP server integration

lessonweaver ships an optional [Model Context Protocol](https://modelcontextprotocol.io)
server so MCP-capable agent runtimes (Claude Code, Copilot, and other clients)
can reach the governed loop in-session: submit a trace, list and read the
resulting review-pending candidates, and load reviewed skills into context.

> The server can **propose** candidates and **load** reviewed skills, but it
> deliberately exposes **no** tool that answers review questions, approves, or
> promotes a skill. Approval stays a human action performed with the CLI.

## Install

The server lives behind an optional extra so the base install stays
dependency-free:

```bash
pip install "lessonweaver[mcp]"
```

`import lessonweaver` never loads the `mcp` SDK; only the server entry point
does. Without the extra, starting the server exits with an install hint.

## Run

```bash
lessonweaver-mcp                       # stdio transport
lessonweaver-mcp --registry-root ./.lessonweaver/registry
lessonweaver-mcp --no-sanitize         # disable submit-time redaction (not recommended)
```

The registry root resolves the same way as the CLI: the `--registry-root` flag,
then the `LESSONWEAVER_REGISTRY` environment variable, then a project-local
`.lessonweaver/registry`, then `~/.lessonweaver/registry`.

### Claude Code client configuration

```json
{
  "mcpServers": {
    "lessonweaver": {
      "command": "lessonweaver-mcp",
      "args": ["--registry-root", "${workspaceFolder}/.lessonweaver/registry"]
    }
  }
}
```

Any MCP client that speaks stdio can launch `lessonweaver-mcp` the same way.

## Tools

| Tool | Effect | Writes? |
| --- | --- | --- |
| `detect` | Mine candidates from a trace bundle | No |
| `submit_trace` | Validate, sanitize, mine, and save candidates as review-pending | Candidates only |
| `list_pending_candidates` | List review-pending candidates | No |
| `get_candidate` | Fetch one candidate by id | No |
| `retrieve` | Rank active skills relevant to a task | No |
| `load_skills` | Compile relevant active skills into a budgeted snippet | No |
| `explain_load` | Explain what would load for a task and why | No |

Each tool maps directly onto the existing public library API
(`LessonDetector`, `FileSystemRegistry`, `SkillRetriever`, `SkillLoader`,
`explain_load`); the server adds no detection, retrieval, or scoring logic of
its own.

## Threat model

Trace content submitted over MCP is **untrusted input**. `submit_trace` runs
[`TraceSanitizer`](../../src/lessonweaver/sanitization.py) on the bundle before
mining by default; pass `--no-sanitize` (or `"sanitize": false` per call) only
when you understand the risk. See the instruction-poisoning notes referenced
from [`docs/protected-invariants.md`](../protected-invariants.md).

## What the server does not do

- It exposes no tool to answer review questions, approve, or promote a skill —
  approval is CLI-only and human-only.
- It makes no LLM or network calls; every tool is deterministic.
- It does not add the `mcp` SDK to the base install.
