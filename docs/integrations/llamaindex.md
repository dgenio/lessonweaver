# LlamaIndex integration

lessonweaver injects reviewed skills into a LlamaIndex agent's context before a
run. lessonweaver only **produces the snippet** — you decide where it goes and
you keep LlamaIndex as an optional dependency. Nothing is loaded automatically
without review.

LlamaIndex is never a lessonweaver dependency; the integration lives in
[`examples/llamaindex_runtime_loader/`](../../examples/llamaindex_runtime_loader/).

## Pre-task injection pattern

Load relevant reviewed skills for the upcoming task, then prepend the compiled
snippet to the agent's system prompt:

```python
from lessonweaver import FileSystemRegistry, SkillLoader

loader = SkillLoader(registry=FileSystemRegistry())
context = loader.load_for_task(
    task="Answer a question about our refund policy",
    agent_type="customer_service",
    budget_chars=1500,
)

system_prompt = f"You are a helpful assistant.\n\n{context.snippet}"
# agent = ReActAgent.from_tools(tools=[], llm=..., system_prompt=system_prompt)
```

`context.snippet` is budget-bounded; `context.included_skills` and
`context.omitted_skills` tell you what fit.

## Post-task trace collection (future work)

After a run you can record the session as a `TraceBundle` and feed it to
`lessonweaver detect` to mine new candidates. A concrete LlamaIndex callback
importer is not provided yet — see the importer design issue
[#52](https://github.com/dgenio/lessonweaver/issues/52).

## Dependency note

Install LlamaIndex separately (`pip install llama-index`). The example uses
`try/except ImportError` so the lessonweaver portion runs without it.

## What lessonweaver does not do

- It does not call an LLM or run the agent for you.
- It does not auto-inject unreviewed skills; only reviewed, active skills are
  retrieved at runtime.
