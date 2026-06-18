# Interoperability

lessonweaver can consume sample trace artifacts produced by sibling tools
**without adding any runtime dependency**. The only contract is the documented
[trace format](trace-format.md): any tool that can emit (or be mapped to) that
JSON shape can feed the detection loop.

## The contract

A trace is a plain JSON object with `trace_id`, `source`, `task`, `events`, and
`outcome`. Unknown fields are ignored, so producers may attach extra metadata
without breaking lessonweaver. `validate_trace_dict` reports any problems.

## Pattern: map an external finding to a trace

A repository checker or gate (for example a sibling tool such as
`dgenio/vibeguard`) emits a structured finding. Map it to a trace where the
finding is an `evaluation_result` or `error` event and the human fix is a
`human_correction` event:

```json
{
  "trace_id": "vibeguard-finding-0001",
  "source": "vibeguard",
  "task": "Review agent-generated change before merge",
  "events": [
    {"id": "f1", "type": "evaluation_result", "status": "failed",
     "content": "Hardcoded secret detected in config loader.",
     "metadata": {"finding_id": "VG-SECRET-01", "severity": "high", "path": "src/config.py"}},
    {"id": "f2", "type": "human_correction",
     "content": "Replaced hardcoded secret with environment variable lookup."}
  ],
  "outcome": "corrected_by_human"
}
```

Then run the normal loop:

```bash
lessonweaver detect vibeguard-finding-0001.json
```

The failed evaluation and the human correction each produce a conservative
candidate you can review and, if the pattern recurs, promote into a reviewed
lesson.

## What this is not

- **Not a hard integration.** lessonweaver takes no dependency on any sibling
  tool; the mapping lives in your script or in `examples/`, never in core.
- **Not automatic promotion.** A single finding is evidence, not a skill. Human
  review remains required. See
  [when not to create a skill](when-not-to-create-a-skill.md).

A generic `TraceImporter` protocol formalizes these mappings; see
[adapters](adapters.md) for the contract and the built-in importers. Concrete,
dependency-free adapters for sibling tools (vibeguard, agent-kernel, ChainWeaver)
live in [`examples/interop_adapters/`](../examples/interop_adapters/). A small
JSON-to-trace mapping function is still all that a one-off needs. See
[ecosystem](ecosystem.md) for related tool boundaries. For a Puppetmaster-style
orchestrator mapping, see the
[Puppetmaster trace ingestion pattern](integrations/puppetmaster.md).
