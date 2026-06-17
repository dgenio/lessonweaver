# Cursor project rules integration

lessonweaver can export a reviewed skill as a Cursor project rule for
`.cursor/rules/*.mdc`.

```bash
lessonweaver export-skill skill-trace-gh-pr-review-001-human-correction \
  --format cursor \
  --applies-to "src/**/*.py" \
  --redact \
  --registry-root /tmp/lw \
  --output .cursor/rules/skill-trace-gh-pr-review-001-human-correction.mdc
```

The generated `.mdc` file contains YAML frontmatter and reviewed Markdown
guidance:

```md
---
description: "Inspect changed files before reviewing pull requests."
globs: "src/**/*.py"
alwaysApply: false
---

# Pull request diff-first review discipline
```

## Scope and activation

- `description` comes from the reviewed skill description.
- `globs` comes from `--applies-to`; pass an empty value to omit the field.
- `alwaysApply` is `false` by default so Cursor can apply the rule based on
  scope and relevance instead of loading every reviewed lesson globally.

## Review boundary

Cursor rules are a native editor surface, but lessonweaver still only exports
reviewed guidance. It does not manage the `.cursor/rules/` directory, delete old
rules, or activate unreviewed candidates. Commit generated `.mdc` files like any
other project instruction change.
