# GitHub Copilot integration

lessonweaver exports reviewed skills into the two instruction surfaces GitHub
Copilot reads. lessonweaver only **generates the text** — you decide where to
put it and you review it before committing. Nothing is written or committed
automatically.

> **Do not paste raw trace evidence into instructions.** Export with `--redact`
> and read the fragment before committing it. Instruction files are loaded into
> every Copilot interaction, so they must not contain secrets or PII.

## Repository-wide instructions (`.github/copilot-instructions.md`)

Loaded for all Copilot interactions in the repo. Generate a block with:

```bash
lessonweaver export-skill <skill-id-or-json> --format copilot-repo --redact
```

The output is a Markdown block with an HTML comment header (carrying the skill
id and version for future deduplication), a `##` title, the description, apply /
do-not-apply conditions, and an instruction list. Append it under a clearly
marked section of `.github/copilot-instructions.md` and commit it like any other
change.

## Path-specific instructions (`.github/instructions/*.instructions.md`)

Loaded only for interactions matching specific file paths. Generate a file with:

```bash
lessonweaver export-skill <skill-id-or-json> --format copilot-path \
  --applies-to "src/**/*.py" --redact
```

The output includes `applyTo` frontmatter scoping the instructions to the glob
you pass with `--applies-to` (default `**`). Save it as
`.github/instructions/<skill-id>.instructions.md`.

## What lessonweaver does not do

- It does not call the GitHub API or commit files for you.
- It does not integrate with the VS Code extension.
- Copilot instruction formats may evolve; treat exports as a reviewed starting
  point, not a guaranteed contract.
