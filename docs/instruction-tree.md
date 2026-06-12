# Instruction tree initialization

`init-agents-tree` scaffolds a root `AGENTS.md` for hierarchical project
guidance. The default profile is Dox-compatible Markdown, but lessonweaver does
not depend on Dox or any agent host.

```bash
lessonweaver init-agents-tree --profile dox
```

The command creates `AGENTS.md` with placeholders for repo-wide contracts,
reviewed lessons, verification notes, and child instruction files. It refuses to
overwrite an existing file unless `--force` is passed:

```bash
lessonweaver init-agents-tree --path AGENTS.md --dry-run
lessonweaver init-agents-tree --path AGENTS.md --force
```

## Workflow

1. Initialize the root instruction tree.

   ```bash
   lessonweaver init-agents-tree --profile dox --path AGENTS.md
   ```

2. Export reviewed lessons into the relevant scope.

   ```bash
   lessonweaver export-skill <skill-id> --format agents-md --registry-root .lessonweaver
   ```

   Put repo-wide guidance in the root `AGENTS.md`. Put narrower contracts in a
   child `AGENTS.md` near the directory where they apply.

3. Validate the tree with external tooling if your agent host provides it.

   lessonweaver only scaffolds and exports reviewed Markdown. It does not choose
   all child boundaries automatically, rewrite existing instructions without
   `--force`, or activate unreviewed findings as durable guidance.
