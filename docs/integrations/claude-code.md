# Claude Code integration

lessonweaver imports reviewed Claude Code hook/transcript evidence into its
trace model, and exports reviewed skills into the three instruction mechanisms
Claude Code reads. lessonweaver does not install hooks or generated
instructions for you: it generates artifacts that you review and place
yourself.

> Claude Code formats may change. Treat these exports as reviewed project
> guidance and a starting point, not a guaranteed contract.

## Which format to use

| Format | CLI `--format` | Target | When to use |
| --- | --- | --- | --- |
| SKILL.md | `claude-skill` | A skill file invokable via the skill system | A self-contained, reusable operational skill |
| Rule fragment | `claude-rule` | `.claude/rules/` | A concise always-on rule loaded automatically |
| CLAUDE.md snippet | `claude-md` | `CLAUDE.md` | Short project-level guidance loaded into every session |

```bash
lessonweaver export-skill <skill-id-or-json> --format claude-skill --redact
lessonweaver export-skill <skill-id-or-json> --format claude-rule --redact
lessonweaver export-skill <skill-id-or-json> --format claude-md --redact
```

`claude-skill` emits a full SKILL.md (when-to-use, when-NOT-to-use,
instructions, anti-patterns, and a metadata section); empty sections are
suppressed. `claude-rule` and `claude-md` emit compact fragments.

The legacy `--format claude` / `claude_skill` still produces the original short
fragment and is kept for backward compatibility.

## Import hook or transcript evidence

Use `ClaudeCodeTraceImporter` when a hook, wrapper script, or transcript export
has captured a coding-agent correction:

```python
from lessonweaver import ClaudeCodeTraceImporter, LessonDetector

payload = {
    "schema": "claude-code/transcript@1",
    "session_id": "cc-42",
    "task": "Fix the auth regression",
    "transcript": [
        {"type": "user", "message": "The login test is failing."},
        {"type": "tool_use", "name": "Edit", "input": {"file_path": "src/auth.py"}},
        {"type": "tool_result", "content": "No match found", "is_error": True},
        {"type": "human_correction", "content": "Use src/login.py instead."},
    ],
}

bundle = ClaudeCodeTraceImporter().import_trace(payload)
candidates = LessonDetector().detect(bundle)
```

The importer maps messages, tool calls/results, errors, retries, final answers,
and human corrections to the documented `TraceBundle` shape. It preserves
source-specific fields in metadata and applies `TraceSanitizer` by default
before detection.

## What lessonweaver does not do

- It does not install skills into Claude Code or register/run hooks.
- It does not test against a real Claude Code installation.
- Always export with `--redact` and review the output before committing —
  these files are loaded into agent context.
