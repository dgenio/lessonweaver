# Dox-compatible AGENTS.md export

Dox uses hierarchical `AGENTS.md` files: a root file holds repo-wide guidance,
and child files hold local contracts for narrower directories. lessonweaver can
export a reviewed skill into that shape without depending on Dox.

```bash
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format dox-agents-md \
  --redact \
  --registry-root /tmp/lw
```

The output is a complete Markdown section or file with this stable structure:

- `Purpose`
- `Ownership`
- `Local Contracts`
- `Work Guidance`
- `Verification`
- `Child Instruction Index`

The leading HTML comment records the lessonweaver profile, skill id, version, and
confidence so future tooling can identify the reviewed block.

## How this differs from `agents-md`

`agents-md` is a compact appendable fragment for an existing instruction file.
Use it when a repo already has a hand-written `AGENTS.md` layout and you only
need a reviewed operational note.

`dox-agents-md` is a hierarchy-friendly section. Use it when the exported skill
is intended to sit at a durable project boundary and should carry ownership,
verification, and child-instruction placeholders with it.

## Governance boundary

The export is Markdown profile compatibility, not a runtime integration:

- no Dox package or runtime dependency is required;
- lessonweaver does not scan directories or choose child boundaries for you;
- unreviewed candidates are not exported as durable guidance;
- reviewed output should still be read before committing it to `AGENTS.md`.
