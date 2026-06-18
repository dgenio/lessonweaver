# Governed learning loop for deployed AI agents

This guide covers production and staging agents that emit telemetry after real
user interactions. The goal is to turn telemetry into reviewed improvements
without autonomous self-training:

```text
telemetry -> trace import -> outcome labeling -> improvement inbox -> review
-> artifact generation -> eval gate -> staged rollout -> effectiveness check
```

lessonweaver is the reviewed-guidance layer in that loop. It does not run the
agent, call an LLM, deploy prompts, or let agents rewrite themselves.

## 1. Connect telemetry or framework traces

Start by normalizing each source into the
[trace format](trace-format.md). For deployed agents, common sources are:

- OpenTelemetry or vendor span exports;
- OpenAI Agents SDK run logs;
- LlamaIndex callback traces;
- LangChain or LangGraph run traces;
- support transcripts paired with evaluator or human-review outcomes.

The preferred import shape is an offline JSON file, not a live receiver. Keep
framework dependencies outside core lessonweaver. Adapter code should map source
events onto `TraceBundle` and preserve provenance in metadata. See
[Adapters and the trace import contract](adapters.md) and the
[OpenTelemetry import design](design/opentelemetry-import.md).

## 2. Import traces into lessonweaver

After normalization, run detection against the trace:

```bash
lessonweaver detect examples/deployed_agent_learning/refund_policy_trace.json \
  --save \
  --registry-root .lessonweaver
```

For framework exports that are not yet native `TraceBundle` JSON, use a small
offline adapter that implements the `TraceImporter` protocol, writes one
canonical trace per run, and then calls the same command. Do not import raw
production payloads into durable instructions.

## 3. Label outcomes

Outcome labels make telemetry useful. At minimum, keep these signals:

- whether the interaction succeeded, failed, or required human correction;
- the evaluator result, if an eval or safety checker ran;
- the user-facing impact;
- the final human disposition;
- the source run id, trace id, environment, and agent version.

In canonical traces, use events such as `evaluation_result`,
`human_correction`, `error`, `retry`, and `workflow_step`. Use
`outcome: "corrected_by_human"` when a human fix was needed.

## 4. Review the improvement inbox

Treat detected candidates as an inbox, not as instructions. Reviewers should
triage each candidate into the right artifact type:

| Artifact type | Use when | Example |
| --- | --- | --- |
| Prompt lesson / skill | A narrow, repeated behavior should be loaded before similar tasks. | "Check refund policy version before answering policy questions." |
| Guardrail | A behavior must be blocked or escalated. | "Never invent eligibility dates." |
| Handoff rule | The agent should route to a human or specialist. | "Escalate when policy source is missing or contradictory." |
| Retrieval rule | The answer depends on fresh external context. | "Retrieve the current policy before quoting terms." |
| Workflow change | The agent process needs a structural step. | "Run policy lookup before composing final answer." |
| Eval | The failure can be caught with fixed inputs and expected outcomes. | "A stale policy answer should fail the regression suite." |
| Memory | The issue is a user fact or preference, not operational guidance. | "Remember the user's preferred language." |
| Reject | The event is one-off, noisy, already covered, or unsafe to generalize. | "A single malformed test request." |

Prefer evals, guardrails, workflow changes, or reject when a runtime prompt
lesson would be too broad. See
[When not to create a skill](when-not-to-create-a-skill.md).

## 5. Generate framework-specific artifacts

Once a reviewer approves the candidate, export the artifact for the framework
that owns the next run.

### OpenAI Agents SDK

Load reviewed skills before constructing agent instructions:

```python
from lessonweaver import FileSystemRegistry, SkillLoader

loader = SkillLoader(registry=FileSystemRegistry())
context = loader.load_for_task(
    task="Answer refund-policy questions",
    agent_type="customer_service",
    tools=["policy_search"],
    budget_chars=1500,
)

instructions = f"You answer customer policy questions.\n\n{context.snippet}"
```

See [OpenAI Agents SDK integration](integrations/openai-agents.md).

### LlamaIndex

Prepend the reviewed snippet to the agent or chat engine system prompt:

```python
from lessonweaver import FileSystemRegistry, SkillLoader

context = SkillLoader(FileSystemRegistry()).load_for_task(
    task="Answer a refund policy question",
    agent_type="customer_service",
    budget_chars=1500,
)

system_prompt = f"You are a support assistant.\n\n{context.snippet}"
```

See [LlamaIndex integration](integrations/llamaindex.md).

### LangChain and LangGraph

Use the same pre-task loading pattern: call `SkillLoader.load_for_task(...)`
before invoking the chain or graph, then append `context.snippet` to the system
message or graph state that feeds the next agent node. Keep LangChain/LangGraph
imports in your adapter or application code, not in lessonweaver core.

For non-skill outcomes, export a reviewed eval, guardrail, or workflow artifact:

```bash
lessonweaver export-lesson candidate-id --format eval \
  --redact --registry-root .lessonweaver

lessonweaver export-lesson candidate-id --format guardrail \
  --redact --registry-root .lessonweaver

lessonweaver export-lesson candidate-id --format workflow \
  --redact --registry-root .lessonweaver
```

## 6. Run evals before rollout

Before enabling a reviewed lesson in production, prove that it loads only where
it should and catches the original failure mode:

```bash
lessonweaver validate-skill examples/coding_agent_pr_review/validation_suite.json \
  --skills-dir examples/coding_agent_pr_review

lessonweaver explain-load "Answer a refund-policy question" \
  --agent-type customer_service \
  --tools policy_search \
  --registry-root .lessonweaver
```

Pair lessonweaver retrieval validation with your external eval runner. A
candidate whose best control is an eval should become an eval artifact and run
in that eval system, not a runtime skill.

## 7. Stage rollout and canary metadata

Record rollout metadata with the approved artifact before broad activation:

- source trace ids and run ids;
- reviewer and approver;
- target framework and agent version;
- environment (`staging`, `canary`, `production`);
- rollout percentage or cohort;
- expected success metric;
- rollback trigger;
- expiration or review date.

Start in staging, then a small canary. Keep the skill status out of broad
runtime loading until the eval gate and canary are reviewed.

## 8. Measure effectiveness and clean up

After rollout, log whether the loaded skill helped:

```bash
lessonweaver record-usage skill-id run-123 \
  --task "Answer refund-policy question" \
  --outcome "answered with current policy" \
  --positive \
  --registry-root .lessonweaver
```

Then review stale or noisy guidance:

```bash
lessonweaver cleanup-skills --registry-root .lessonweaver
```

Retire or narrow skills that no longer load, load for unrelated tasks, overlap
with stronger policy, or correlate with negative outcomes.

## Example

The fixture in
[`examples/deployed_agent_learning/refund_policy_trace.json`](../examples/deployed_agent_learning/refund_policy_trace.json)
shows a support agent answering from a stale refund policy. The reviewed artifact
in
[`examples/deployed_agent_learning/refund_policy_artifact.md`](../examples/deployed_agent_learning/refund_policy_artifact.md)
shows the resulting framework-neutral prompt lesson, rollout metadata, eval
gate, and rollback signal.

The important boundary is the same as production: the trace is evidence, the
artifact is reviewed guidance, and a separate rollout gate decides whether it
enters the deployed agent context.
