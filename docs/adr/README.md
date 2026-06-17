# Architecture Decision Records

Architecture decision records capture the reasoning behind durable project
constraints. They are intentionally short: enough context for future reviewers
to understand why a choice exists, what code embodies it, and what tradeoffs it
accepts.

## Process

- New significant architecture changes should add a new ADR or supersede an
  existing one.
- Accepted ADRs are not rewritten for new decisions. Create a superseding ADR
  and link both records instead.
- Keep records one page when possible, using the template in
  [`template.md`](template.md).

## Records

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-deterministic-core.md) | Accepted | Keep the core deterministic and LLM-free |
| [0002](0002-human-review-gate.md) | Accepted | Require human review before activation |
| [0003](0003-conservative-detection.md) | Accepted | Prefer conservative lesson detection |
| [0004](0004-zero-runtime-dependencies.md) | Accepted | Keep runtime dependencies out of the core |
| [0005](0005-filesystem-json-registry.md) | Accepted | Use filesystem JSON as the reference registry |
| [0006](0006-lexical-retrieval-baseline.md) | Accepted | Keep lexical retrieval as the deterministic baseline |
| [0007](0007-diff-first-file-merging.md) | Accepted | Use diff-first managed file merging |
