# ADR-0004: Keep Runtime Dependencies Out Of The Core

## Status

Accepted

## Context

`pyproject.toml` has no required runtime dependencies, while developer tools
live under the `dev` optional dependency group. AGENTS.md says integrations
belong in `examples/` and optional framework packages must not become core
dependencies. `importers.py` defines dependency-free protocols and conversion
paths rather than importing specific frameworks.

## Decision

The installable core remains dependency-free at runtime. Third-party framework,
LLM, telemetry, and embedding packages belong in examples or optional extras
behind explicit interfaces.

## Consequences

Users can import and run the library in small, locked-down environments.
Integrations take a little more ceremony because they cannot rely on implicit
core dependencies. Any proposed runtime dependency must justify why an optional
extra is insufficient and must include import-graph or packaging tests.
