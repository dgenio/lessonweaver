# OpenAI Agents SDK integration

lessonweaver injects reviewed skills into an OpenAI Agents SDK agent's
instructions before a run. lessonweaver only **produces the snippet** — you
decide where it goes and you keep the SDK as an optional dependency. Nothing is
loaded automatically without review.

The OpenAI Agents SDK is never a lessonweaver dependency; the integration lives
in [`examples/openai_agents_runtime_loader/`](../../examples/openai_agents_runtime_loader/).

## Pre-task injection pattern

Load relevant reviewed skills for the upcoming task, then add the compiled
snippet to the agent's instructions:

```python
from lessonweaver import FileSystemRegistry, SkillLoader

loader = SkillLoader(registry=FileSystemRegistry())
context = loader.load_for_task(
    task="Review this pull request for missing tests",
    agent_type="coding",
    tools=["github"],
    budget_chars=1500,
)

instructions = f"You review pull requests.\n\n{context.snippet}"
# agent = Agent(name="reviewer", instructions=instructions)
```

`context.snippet` is budget-bounded; `context.included_skills` and
`context.omitted_skills` tell you what fit. No API key is needed to build the
instructions; only the actual agent run requires one.

## Post-task trace collection (future work)

After a run you can record the session as a `TraceBundle` and feed it to
`lessonweaver detect` to mine new candidates. A concrete Agents-SDK trace
importer is not provided yet — see the importer design issue
[#52](https://github.com/dgenio/lessonweaver/issues/52).

## Dependency note

Install the SDK separately (`pip install openai-agents`). The example uses
`try/except ImportError` so the lessonweaver portion runs without it.

## What lessonweaver does not do

- It does not call an LLM or run the agent for you.
- It does not auto-inject unreviewed skills; only reviewed, active skills are
  retrieved at runtime.
