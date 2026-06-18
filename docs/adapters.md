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
| `OpenTelemetryImporter` | OTLP JSON export, flat span JSON, or JSONL spans | maps deployed-agent span semantics to trace evidence |

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
5. **Keep it optional.** Concrete adapters for external systems live in
   `examples/`, never in core (see [interoperability](interoperability.md)).

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

## OpenTelemetry agent traces

`OpenTelemetryImporter` accepts OTLP-style `resourceSpans`, flat `{"spans": [...]}`
payloads, a single span object, or newline-delimited JSON spans. It recognizes
common AI-agent semantic attributes without requiring an OpenTelemetry SDK:

| Semantic input | Trace event |
| --- | --- |
| `gen_ai.*`, `llm.*`, or span names like `llm.chat` | `model_call` |
| `tool.name`, `gen_ai.tool.name`, or span names containing `tool` | `tool_call` |
| `retrieval.*` or span names containing `retrieval` | `tool_call` with retrieval metadata |
| `agent.handoff.from` / `agent.handoff.to` | `workflow_step` |
| `guardrail.name` / `guardrail.result` | `evaluation_result` |
| span events named `human_feedback` or `human_correction` | `human_correction` |
| span status `ERROR` or `error.type` | `error` |

Missing optional fields are tolerated and listed under
`metadata["otel"]["warnings"]`. Sensitive span attributes such as authorization
headers, tokens, API keys, passwords, and secrets are redacted by default.

```bash
lessonweaver import-otel examples/opentelemetry/minimal_agent_trace.json

# JSONL span export
lessonweaver import-otel spans.jsonl --jsonl
```

## Known future adapter candidates

- **Sibling tools** — agent-kernel ActionTrace, ChainWeaver flow-failure, and
  vibeguard finding adapters live in
  [`examples/interop_adapters/`](../examples/interop_adapters/).
- Claude Code hooks, Pipecat post-call JSON, CI logs.
