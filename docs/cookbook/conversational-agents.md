# Cookbook: Conversational Agents

Practical recipes for using lessonweaver with support chatbots and voice
agents. The adoption path is the same as for coding agents:

> failed or corrected conversation -> reviewed lesson -> runtime prompt snippet
> or guardrail -> future agent behavior.

**lessonweaver never injects unreviewed guidance automatically.** Every recipe
below uses a temporary registry and ends at an artifact you review before loading
it into a chatbot, prompt store, or voice-agent runtime.

## Shared setup

These examples use only bundled traces and write registry state under `/tmp`.

```bash
rm -rf /tmp/lw-chatbot-cookbook /tmp/lw-voice-cookbook
```

## 1. Support chatbot policy-version skill

The chatbot trace contains a failed evaluation for a policy answer. Detection
classifies it as an eval candidate by default, so the review step explicitly
chooses `action_type=skill` before approval.

```bash
lessonweaver review-trace examples/traces/external_chatbot_policy_failure.json \
  --registry-root /tmp/lw-chatbot-cookbook \
  --answer scope=project \
  --answer action_type=skill \
  --answer risk_level=high \
  --answer approval_requirement=explicit_approval \
  --answer applicability=high_risk \
  --answer negative_conditions=different_domain \
  --answer decision=approve \
  --approve \
  --approved-by reviewer
```

Expected review result excerpt:

```json
{
  "approval": {
    "candidate_id": "trace-chatbot-policy-001-failed-eval",
    "lesson_id": "lesson-trace-chatbot-policy-001-failed-eval",
    "skill_id": "skill-trace-chatbot-policy-001-failed-eval"
  },
  "trace_id": "trace-chatbot-policy-001"
}
```

Promote the approved skill before runtime use so loaders include it:

```bash
lessonweaver promote-skill skill-trace-chatbot-policy-001-failed-eval active \
  --registry-root /tmp/lw-chatbot-cookbook
```

Export the active skill as a runtime prompt snippet:

```bash
lessonweaver export-skill skill-trace-chatbot-policy-001-failed-eval \
  --format runtime \
  --redact \
  --registry-root /tmp/lw-chatbot-cookbook
```

Reviewed runtime artifact:

```text
Operational lesson:
Candidate lesson based on failed evaluation_result signal.
Applies when: Candidate lesson based on failed evaluation_result signal.
Do not apply when: When the task is unrelated to the observed trace context.
Required behaviors: Possible reusable pattern: add stronger retrieval/version checks before answering.
```

A chatbot runtime can load active reviewed skills before serving a policy task:

```python
from lessonweaver import FileSystemRegistry, SkillLoader

loader = SkillLoader(registry=FileSystemRegistry("/tmp/lw-chatbot-cookbook"))
context = loader.load_for_task(
    task="Answer a customer refund-policy question from current policy docs",
    agent_type="chatbot",
    budget_chars=600,
)
system_prompt = context.snippet
```

The repo also includes a hand-written destination artifact for this scenario:
[`examples/skills/chatbot_policy_version_check.md`](../../examples/skills/chatbot_policy_version_check.md).

## 2. Voice slot-correction guardrail

The voice trace shows a user correcting a misheard appointment slot. The review
step chooses a guardrail artifact so the exported lesson can block repeating the
same conversational failure.

```bash
lessonweaver review-trace examples/traces/voice_slot_correction.json \
  --registry-root /tmp/lw-voice-cookbook \
  --answer scope=project \
  --answer action_type=guardrail \
  --answer risk_level=medium \
  --answer applicability=always \
  --answer negative_conditions=different_domain \
  --answer decision=approve
```

Expected review result excerpt:

```json
{
  "approval": null,
  "candidates": [
    {
      "candidate_id": "trace-voice-slot-001-human-correction",
      "remaining_questions": [],
      "review_complete": true,
      "status": "approved"
    }
  ],
  "trace_id": "trace-voice-slot-001"
}
```

Export the reviewed candidate as a guardrail:

```bash
lessonweaver export-lesson trace-voice-slot-001-human-correction \
  --format guardrail \
  --redact \
  --registry-root /tmp/lw-voice-cookbook
```

Reviewed guardrail artifact:

```markdown
# Guardrail: Candidate lesson based on observed correction by a human reviewer.

## Trigger condition
Agent required explicit human correction before reaching acceptable behavior.

## Blocked behavior
Completing the task without applying the corrective check below.

## Rationale
Possible reusable pattern: incorporate the corrected check earlier in similar tasks.

## Evidence
- trace: trace-voice-slot-001
```

The repo also includes a reviewed skill example for this scenario:
[`examples/skills/voice_slot_repair.md`](../../examples/skills/voice_slot_repair.md).
For voice-specific runtime constraints, see the
[Pipecat integration guide](../integrations/pipecat.md).

## What differs from coding agents

- Conversational agents usually load short runtime snippets or prompt-store
  entries instead of writing instruction files such as `AGENTS.md`.
- Voice agents have a tighter latency budget, so prefer summary or name-only
  loading and keep per-turn hints to one sentence.
- Chatbot and voice traces often produce eval or guardrail candidates first;
  choose `action_type=skill` during review only when the lesson should become
  durable runtime guidance.
- Keep the same governance rule: no unreviewed trace output is loaded into a
  live agent.
