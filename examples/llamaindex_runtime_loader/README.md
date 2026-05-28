# LlamaIndex runtime skill loading

A self-contained example showing how to load reviewed lessonweaver skills into a
LlamaIndex agent's system prompt before a run. LlamaIndex is an **optional**
dependency — the example runs and demonstrates the lessonweaver portion even
when LlamaIndex is not installed.

Tracking issue: [#20](https://github.com/dgenio/lessonweaver/issues/20).
See also [docs/integrations/llamaindex.md](../../docs/integrations/llamaindex.md).

## Install

```bash
pip install -e ".[dev]"        # lessonweaver itself
pip install llama-index        # optional, for the integration branch
```

LlamaIndex is **not** added to lessonweaver's dependencies; framework
integrations stay in `examples/` by design.

## Run

```bash
python examples/llamaindex_runtime_loader/example.py
```

Without LlamaIndex you will see the loaded skill context and a note. With
LlamaIndex installed you also see how the snippet would be injected into a
system prompt.

## How it works

1. `SkillLoader` reads the bundled `example_registry/` (one reviewed, active
   skill) — not your home directory.
2. `load_for_task(...)` retrieves and compiles the relevant skills into a short
   `context.snippet` within a character budget.
3. The snippet is prepended to the agent's system prompt before the run.

## Files

- `example.py` — the runnable example with an optional LlamaIndex branch.
- `example_registry/skills/skill-refund-policy.json` — one reviewed, active
  skill used by the example.

## Out of scope

- Real LlamaIndex agent execution and post-call trace mining.
- Any real user data — the bundled skill is fully synthetic.
