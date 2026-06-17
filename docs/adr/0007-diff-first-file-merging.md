# ADR-0007: Use Diff-First Managed File Merging

## Status

Accepted

## Context

`filemerge.py` wraps exported skill content in managed sentinels, updates those
blocks idempotently, and returns unified diffs for preview. Its module docstring
states that writing is never implicit: callers render merged text and a diff,
then persist only when the user opts in.

## Decision

Instruction-file exports must remain diff-first and explicit-write. Managed
blocks may update generated content in place, but they must not clobber
hand-written content or silently write files as a side effect of rendering.

## Consequences

Users can review changes before agent instructions are modified. This reduces
the risk of accidental context changes at the cost of an extra confirmation step
for automated workflows. New exporters should return text, diffs, or artifacts;
write operations must stay explicit in the calling command or API.
