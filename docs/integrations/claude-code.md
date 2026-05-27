# Claude Code integration

lessonweaver exports reviewed skills into the three instruction mechanisms
Claude Code reads. lessonweaver is an **export tool**, not a Claude Code
integration: it generates text that you review and place yourself. Nothing is
installed or committed automatically.

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

## What lessonweaver does not do

- It does not install skills into Claude Code or run hooks.
- It does not test against a real Claude Code installation.
- Always export with `--redact` and review the output before committing —
  these files are loaded into agent context.
