# OpenAI Agents SDK runtime skill loading

A self-contained example showing how to load reviewed lessonweaver skills into an
OpenAI Agents SDK agent's instructions before a run. The SDK is an **optional**
dependency — the example runs and demonstrates the lessonweaver portion even when
the SDK is not installed. No API key is required to understand it.

Tracking issue: [#21](https://github.com/dgenio/lessonweaver/issues/21).
See also [docs/integrations/openai-agents.md](../../docs/integrations/openai-agents.md).

## Install

```bash
pip install -e ".[dev]"        # lessonweaver itself
pip install openai-agents      # optional, for the integration branch
```

The OpenAI Agents SDK is **not** added to lessonweaver's dependencies; framework
integrations stay in `examples/` by design.

## Run

```bash
python examples/openai_agents_runtime_loader/example.py
```

Without the SDK you will see the loaded skill context and a note. With the SDK
installed you also see how the snippet would be injected into agent instructions.

## How it works

1. `SkillLoader` reads the bundled `example_registry/` (one reviewed, active
   skill) — not your home directory.
2. `load_for_task(...)` retrieves and compiles the relevant skills into a short
   `context.snippet` within a character budget.
3. The snippet is added to the agent's `instructions` before the run. The actual
   agent call stays commented out so no API key is needed.

## Files

- `example.py` — the runnable example with an optional OpenAI Agents SDK branch.
- `example_registry/skills/skill-pr-review.json` — one reviewed, active skill
  used by the example.

## Out of scope

- A real agent run, tool calls, or API key handling.
- Any real user data — the bundled skill is fully synthetic.
