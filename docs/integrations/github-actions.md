# GitHub Actions integration

Use the lessonweaver governance action to enforce reviewed-skill hygiene in CI.
The action is a composite action: it sets up Python, installs lessonweaver, runs
skill lint, runs retrieval validation suites, and checks existing managed
instruction blocks for drift. Results are printed to the job log and summarized
in `$GITHUB_STEP_SUMMARY`.

## Lint-only workflow

```yaml
name: lessonweaver

on:
  pull_request:

permissions:
  contents: read

jobs:
  lint-skills:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dgenio/lessonweaver@v1
        with:
          skills-dir: .lessonweaver/skills
```

## Full governance gate

```yaml
name: lessonweaver

on:
  pull_request:

permissions:
  contents: read

jobs:
  governance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dgenio/lessonweaver@v1
        with:
          registry-root: .lessonweaver/registry
          skills-dir: .lessonweaver/skills
          validation-suites: tests/lessonweaver/*.json
          instruction-files: |
            AGENTS.md
            CLAUDE.md
            .github/copilot-instructions.md
```

The drift check only examines existing `lessonweaver:begin` managed blocks. If a
block has been hand-edited, the action fails and prints the unified diff needed
to restore the exported content. In repositories that install lessonweaver from
source, override `install-command`; this repository's dogfood workflow uses
`python -m pip install -e .`.
