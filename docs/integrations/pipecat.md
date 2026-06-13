# Pipecat voice agent integration

Voice agents built with Pipecat have constraints text agents do not:

- **Latency.** Anything injected into a spoken turn must be short or the agent
  sounds robotic.
- **Slot repair.** When a user corrects a misheard value ("No, I said Tuesday,
  not Thursday"), the agent must repair that one slot cleanly.
- **Post-call mining.** Voice sessions produce transcription traces that can be
  mined for lessons after the call ends.

lessonweaver only **produces reviewed guidance**; it does not run the voice
pipeline and is never a Pipecat dependency.

## Pre-session skill loading

Load short skills into the system context **before** the session starts. Keep
them terse to protect the latency budget by using a name-only or summary
inclusion level and a small character budget:

```python
from lessonweaver import FileSystemRegistry, SkillLoader

loader = SkillLoader(registry=FileSystemRegistry())
context = loader.load_for_task(
    task="Book a service appointment from spoken input",
    agent_type="voice",
    budget_chars=400,
    inclusion_level="summary",   # or "name_only" for the tightest budget
)
system_context = context.snippet
```

## Per-turn hints

If you must add guidance mid-session, inject at most a one-sentence reminder at
the start of a turn and keep `budget_chars` around 100 so spoken latency stays
low.

## Post-call trace mining

After the call ends, record the session transcript as a `TraceBundle` and run
detection on it:

```bash
lessonweaver detect examples/traces/voice_slot_correction.json
```

[`examples/traces/voice_slot_correction.json`](https://github.com/dgenio/lessonweaver/blob/main/examples/traces/voice_slot_correction.json)
is a concrete voice trace: the agent mishears both the time and the location, the
user corrects it, and detection produces one `human_correction` candidate.

## Conversational repair skill

[`examples/skills/voice_slot_repair.md`](https://github.com/dgenio/lessonweaver/blob/main/examples/skills/voice_slot_repair.md)
is an example reviewed skill for slot correction. It repairs only the corrected
slot and confirms in a single short sentence to respect the latency budget.

## What lessonweaver does not do

- It does not run the Pipecat pipeline, TTS, or STT.
- It does not auto-inject unreviewed skills; only reviewed skills are loaded, and
  you choose the inclusion level and budget.
