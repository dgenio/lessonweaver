# ADR-0001: Keep The Core Deterministic And LLM-Free

## Status

Accepted

## Context

lessonweaver turns traces into reusable lessons that may later influence agent
behavior. The README describes the core as deterministic with no LLM calls, and
AGENTS.md repeats that detection, interview, linting, retrieval, and analysis
must stay deterministic. The current implementation matches that boundary:
`detection.py`, `interview.py`, `lint.py`, `retrieval.py`, `analysis.py`,
`compile.py`, and `loader.py` use local rules and data structures.

## Decision

The core package must not call LLMs, embedding services, remote telemetry
systems, or network APIs. ML and LLM assistance may exist only as optional
layers around the core, with explicit opt-in and deterministic fallbacks.

## Consequences

The default behavior is reproducible, testable, and safe to run in CI or local
developer workflows without credentials. The tradeoff is that drafting,
clustering, and retrieval quality starts with conservative heuristics instead
of model output. Future model-backed features must preserve the default
deterministic path and make provider use visible to reviewers.
