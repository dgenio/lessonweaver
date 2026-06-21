# ADR-0006: Keep Lexical Retrieval As The Deterministic Baseline

## Status

Accepted

## Context

`retrieval.py` describes `SkillRetriever` as ranking active skills with a
deterministic lexical baseline. The implementation tokenizes the task and skill
metadata, applies status, scope, and risk filters, and reports why skills were
selected or skipped. Embedding retrieval is tracked separately as optional
future work.

## Decision

Lexical retrieval remains the default and fallback retrieval path. Embedding or
model-backed retrieval may layer on through an explicit optional interface, but
it must not replace the deterministic baseline.

## Consequences

Retrieval behavior is explainable and can run without credentials. The tradeoff
is lower semantic recall than embedding search. Future retrieval work should
compare against this baseline and preserve diagnostics that tell users why a
skill loaded or was skipped.
