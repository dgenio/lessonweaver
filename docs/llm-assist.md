# LLM Assist Boundary

lessonweaver's core pipeline stays deterministic and human-gated. Optional
LLM-assisted extensions can draft summaries, review questions, or downstream
artifacts, but they must follow one product principle:

> The LLM proposes, the system checks, the human approves, the runtime obeys.

## Default Safety Contract

- Assist mode is disabled by default. Callers must construct
  `LLMAssistConfig(enabled=True)` before any provider receives evidence.
- Trace evidence is scrubbed with `TraceSanitizer` before provider calls unless
  a caller explicitly disables redaction.
- Every returned `LLMAssistSuggestion` is marked `llm_assisted=True` and
  `authoritative=False`.
- Suggestions carry provider, model, model version, prompt id, redaction status,
  and creation time for auditability.
- Assist metadata is safe to attach to candidates, lessons, or skills, but it
  does not contain lifecycle fields such as `status`, `approved_by`, or
  `approved_at`.
- No assist provider can approve a candidate, promote a skill, activate a skill,
  or roll out a lesson. Those actions remain deterministic review and governance
  paths.

## Provider Shape

Providers implement the small `LLMAssistProvider` protocol:

```python
from lessonweaver import LLMAssistClient, LLMAssistConfig

client = LLMAssistClient(provider=provider, config=LLMAssistConfig(enabled=True))
suggestion = client.suggest(
    prompt_id="lesson-draft",
    prompt="Draft a candidate lesson from this trace.",
    trace=trace_bundle,
)
```

Tests and offline workflows can use `MockLLMAssistProvider`, which records
redacted requests without making network calls.
