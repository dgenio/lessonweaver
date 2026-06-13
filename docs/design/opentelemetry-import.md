# Design: future OpenTelemetry span import

> **Status: design sketch — no code.** This document captures the mapping
> decisions and open questions for a future OpenTelemetry (OTel) trace importer
> so the design can be reviewed before implementation (issue #27). It does not
> add an OTel dependency.

## 1. Why OTel matters

OpenTelemetry is the emerging standard for distributed tracing in AI-agent
systems. Frameworks such as LangChain/LangSmith, LlamaIndex, and the OpenAI
Agents SDK now emit OTel spans (commonly under the `gen_ai.*` semantic
conventions). Production traces from these frameworks can be collected and
mined — but lessonweaver needs a **mapping layer** onto its
[`TraceBundle`](../trace-format.md) shape, not raw span ingestion. A future
`OpenTelemetryImporter` would implement the
[`TraceImporter`](../adapters.md) protocol.

## 2. OTel → TraceBundle mapping

| OTel concept | TraceBundle field / event |
| --- | --- |
| Trace ID | `trace_id` |
| Root span name | `task` |
| `gen_ai.system` attribute | `source` |
| Inbound message span | `TraceEventType.user_message` |
| Tool-call span (`gen_ai.operation.name = "tool_call"`) | `TraceEventType.tool_call` |
| Model-invocation span | `TraceEventType.assistant_message` / `model_call` |
| Span `status = ERROR` | `TraceEventType.error` |
| Corrective span following an error | `TraceEventType.retry` |
| Root span outcome annotation | `outcome` |

Span start order (by start timestamp) defines event order. Span attributes that
have no trace-schema home are preserved in `TraceEvent.metadata`.

## 3. Candidate signals in OTel spans

How each conservative detection signal would be recognized:

- **Human correction** — a span/annotation attribute marking a manual fix
  (e.g. `gen_ai.event.content` with a correction marker).
- **Failed eval** — an eval span with result = fail → `evaluation_result`
  (`status="failed"`).
- **Error → retry → success** — a model/tool span with `status = ERROR`
  followed by a later sibling span that succeeds.
- **Tool fallback** — a failed tool-call span followed by a successful
  alternative tool-call span.
- **Corrected-by-human outcome** — a root-span outcome annotation.

## 4. Sensitive data handling

OTel spans may carry full user messages and model outputs. Import **must** route
content through the pre-mining sanitizer
([`TraceSanitizer`](https://github.com/dgenio/lessonweaver/blob/main/src/lessonweaver/sanitization.py),
issue #46) before
the content lands in any `TraceEvent`, and respect `SensitivityLevel` so
high-sensitivity content is redacted before storage. Import-time redaction is
required, not optional, because OTel exports are often collected centrally.

## 5. Implementation options

- **Option A — OTLP receiver (pull).** lessonweaver listens for OTLP/HTTP.
  Highest integration cost; turns lessonweaver into a service.
- **Option B — offline OTLP file import.** Read an exported OTLP JSON file and
  map it. Lowest cost, dependency-free (the export is plain JSON), testable with
  fixtures.
- **Option C — SDK instrumentation adapter.** Patch into a framework's tracer.
  Tightest coupling; framework-specific.

**Recommendation: start with Option B** (offline import from OTLP JSON export
files). It fits the protocol cleanly, needs no runtime dependency, and is easy
to fixture in tests.

## 6. Open questions

- Which OTel semantic-convention version(s) to target first (`gen_ai.*` is still
  evolving)?
- How to collapse nested spans (a tool call that wraps model calls) into a flat
  event list without losing the error→recovery ordering?
- Should multi-trace OTLP files map to one `TraceBundle` per trace id (yes,
  initially) and feed multi-trace clustering (#37)?
- Where does redaction policy live — importer config, or a shared sanitizer
  ruleset?

## 7. Out of scope (for the first implementation)

- Streaming / live span import.
- Async import.
- Vendor-specific span extensions beyond the `gen_ai.*` conventions.
