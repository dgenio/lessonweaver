# Sibling interop adapters

These adapters map the **serialized output** of sibling Weaver-stack tools into
lessonweaver's [trace format](../../docs/trace-format.md) so their failures can
be mined for reviewed lessons (issue #91). They are the input side of the
closed loop: siblings *produce* traces/findings → lessonweaver turns them into
governed guidance.

Each adapter:

- implements the core [`TraceImporter`](../../src/lessonweaver/importers.py)
  protocol (`can_import` / `import_trace`);
- takes **no runtime dependency** on the sibling — it maps a plain dict, it does
  not import the sibling package;
- lives here in `examples/`, never in core, per
  [`AGENTS.md`](../../AGENTS.md) and
  [interoperability](../../docs/interoperability.md).

| Adapter | Sibling output | Module |
| --- | --- | --- |
| vibeguard finding | review finding (`finding_id`, `message`, `remediation`) | `vibeguard_finding.py` |
| agent-kernel ActionTrace | ordered `actions` toward a goal | `agent_kernel_actiontrace.py` |
| ChainWeaver flow-failure | flow `steps` with a failing step | `chainweaver_failure.py` |

## Run them

```bash
python examples/interop_adapters/vibeguard_finding.py
python examples/interop_adapters/agent_kernel_actiontrace.py
python examples/interop_adapters/chainweaver_failure.py
```

Each loads its bundled `sample_*.json`, maps it to a `TraceBundle`, and prints
the candidate lessons the detector finds.

## A note on the accepted shapes

The exact serialized schemas live in the sibling repositories
(`dgenio/agent-kernel`, `dgenio/ChainWeaver`, `dgenio/vibeguard`) and are
coordinated through the weaver-spec `FailureCaseArtifact` / `TraceBundle`
contract. The shapes documented in each module's docstring are a **best-effort
mapping** drawn from the sketches in
[interoperability.md](../../docs/interoperability.md); confirm them against the
sibling's current output before relying on an adapter in production. Unknown
keys are ignored, so a shape can carry extra fields without breaking the
mapping.
