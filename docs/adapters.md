# Adapters and the trace import contract

lessonweaver mines a single internal shape: the [`TraceBundle`](trace-format.md).
Real traces arrive in many formats (sibling tools, OpenTelemetry spans, CI
logs, custom loggers). The `TraceImporter` protocol (issue #52) defines one
small, dependency-free contract every importer follows, so importers stay
swappable and testable instead of being designed ad hoc.

## The `TraceImporter` protocol

```python
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class TraceImporter(Protocol):
    def can_import(self, source: dict[str, Any]) -> bool: ...
    def import_trace(self, source: dict[str, Any]) -> TraceBundle: ...
```

- **`can_import`** — cheap recognition. Return `True` only for payloads this
  importer understands (a schema marker, or a structural fingerprint). It must
  not raise.
- **`import_trace`** — convert a recognized payload into a `TraceBundle`. Raise
  `ValueError` with a human-readable message for a recognized-but-invalid
  payload.

Importers are **deterministic and dependency-free**: no network, no LLM, no
importing the source system. They map a dict onto the schema.

## Built-in importers (core)

| Importer | Input | Notes |
| --- | --- | --- |
| `DictTraceImporter` | canonical lessonweaver trace JSON | `load_trace_bundle` delegates to it |
| `FailureCaseImporter` | replayable failure case artifact | governed path for issue #82 |
| `VibeguardReportImporter` | VibeGuard `ArtifactSafetyReport` / native report JSON | preserves finding provenance and only promotes repeated categories through `import-vibeguard` |

`DictTraceImporter` makes the canonical loader a special case of the protocol:
`load_trace_bundle` reads the JSON file, then calls `import_trace`.

## Normalization steps (recommended)

When writing an adapter for a new format:

1. **Identify the trace id, task, and source.** Every bundle needs a stable
   `trace_id`.
2. **Map events.** Translate each source record to a `TraceEventType`. The
   conservative detector keys on these in particular:
   - a human fix → `human_correction`
   - a failed grade/check → `evaluation_result` with `status="failed"`
   - a failure then a recovery → `error` followed by `retry` (with a successful
     outcome), or `tool_call` failure then success
   - a workflow misstep → `workflow_step` (+ a following `error`)
3. **Set the outcome.** Use `corrected_by_human` when a human fix is present,
   otherwise `success` / `failure` / `unknown`.
4. **Preserve provenance.** Put source-specific identifiers in `metadata` (on
   the bundle and/or events). Unknown source fields can be dropped or carried in
   `metadata`; lessonweaver ignores unknown keys.
5. **Keep it optional.** Experimental adapters for external systems live in
   `examples/`; stable plain-JSON report formats may get a first-class core
   importer when they stay dependency-free (see [interoperability](interoperability.md)).

### Required vs optional bundle fields

| Field | Required | Default if omitted |
| --- | --- | --- |
| `trace_id` | yes | — |
| `source` | yes (canonical) | importer-supplied |
| `task` | recommended | `""` |
| `events` | yes (canonical) | `[]` |
| `outcome` | recommended | `"unknown"` |
| `metadata` | no | `{}` |

## The failure case artifact (issue #82)

`FailureCaseImporter` accepts a replayable failure artifact — mirroring the
planned weaver-spec `FailureCaseArtifact` (dgenio/weaver-spec#72) — and maps it
to a bundle so the normal loop applies. Recognized keys:

| Key | Meaning |
| --- | --- |
| `failure_id` (or `id`) | stable id → `trace_id` (required) |
| `failure.summary` / `failure.detail` | becomes a failed `evaluation_result` event |
| `failure.severity` | preserved in provenance |
| `correction.summary` | becomes a `human_correction` event |
| `replay.ref` / `replay.reproducible` | preserved in provenance |
| `task`, `source`, `outcome`, `schema` | optional |

Provenance is stored under `metadata["failure_case"]` and propagated onto every
resulting candidate by `candidates_from_failure_case`. See
[`examples/failure_cases/`](../examples/failure_cases/).

## Known future adapter candidates

- **OpenTelemetry** spans — design sketched in
  [`design/opentelemetry-import.md`](design/opentelemetry-import.md).
- **Sibling tools** — agent-kernel ActionTrace and ChainWeaver flow-failure
  adapters live in [`examples/interop_adapters/`](../examples/interop_adapters/).
  VibeGuard reports have a first-class import command, with single-finding
  adapter examples kept there for lightweight interop demonstrations.
- Claude Code hooks, Pipecat post-call JSON, CI logs.
