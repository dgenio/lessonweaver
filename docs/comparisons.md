# Comparisons

lessonweaver sits next to several crowded categories. It is easy to mistake it
for a replacement for one of them. It is not. This page draws the boundary for
each category: what the category does, where lessonweaver overlaps, where it
does not, and how they work together.

One-line summary:

- **Observability** records what happened.
- **Evals** test behavior under controlled conditions.
- **Memory** stores context for reuse.
- **Agent frameworks** orchestrate actions.
- **lessonweaver** turns *reviewed* trace evidence into governed, reusable
  operational guidance.

For tool-specific integration boundaries, see [ecosystem](ecosystem.md).

## 1. Observability / tracing tools

- **What the category does:** Captures, stores, and visualizes runs, spans,
  latencies, and errors.
- **Overlap:** Both consume execution traces.
- **No overlap:** lessonweaver does not collect live telemetry, store spans, or
  render dashboards. It reads a trace offline and proposes a *lesson*.
- **Together:** Export or normalize traces from an observability tool into the
  [trace format](trace-format.md), then run `lessonweaver detect`.
- **Example:** A dashboard shows a spike in PR-review corrections; lessonweaver
  turns one of those corrected traces into a reviewed "inspect the diff first"
  skill.

## 2. Eval frameworks

- **What the category does:** Runs prompts/agents against fixed cases and scores
  outputs.
- **Overlap:** A reviewed lesson can recommend an eval (`recommended_action_type
  = eval`).
- **No overlap:** lessonweaver does not execute evals or score model output.
- **Together:** Mine real failures into candidate eval specs; run them in your
  eval framework. (Dedicated eval exporters are planned,
  [#47](https://github.com/dgenio/lessonweaver/issues/47).)
- **Example:** A failed `evaluation_result` event becomes a candidate whose
  reviewed action type is "eval", feeding a new regression case.

## 3. Prompt management systems

- **What the category does:** Versions, stores, and deploys prompts/templates.
- **Overlap:** Both produce text destined for agent context.
- **No overlap:** lessonweaver does not host, A/B test, or deploy prompts. It
  produces reviewed *fragments* with provenance and governance metadata.
- **Together:** Paste an exported fragment into your prompt store as a reviewed,
  evidence-backed entry.
- **Example:** An approved skill card is added to a prompt registry with its
  evidence trace IDs and approver recorded.

## 4. Agent memory systems

- **What the category does:** Persists conversational facts/embeddings for
  recall at runtime.
- **Overlap:** Both persist information across runs.
- **No overlap:** Generic memory stores *unreviewed* facts automatically.
  lessonweaver stores only *human-reviewed* lessons with scope, risk, lifecycle,
  and evidence — never raw conversation.
- **Together:** Use memory for recall of facts; use lessonweaver for governed
  operational guidance that must not be applied blindly.
- **Example:** Memory remembers a customer's name; lessonweaver records the
  reviewed rule "confirm a corrected slot value before proceeding."

## 5. Agent orchestration frameworks

- **What the category does:** Defines tools, control flow, and runs agents.
- **Overlap:** Skills are injected into the instructions of agents these
  frameworks run.
- **No overlap:** lessonweaver does not orchestrate, call models, or own the run
  loop, and adds no framework dependency.
- **Together:** Call `SkillLoader.load_for_task(...)` before a run and inject the
  snippet into the framework's instruction mechanism.
- **Example:** Before a coding-agent run, load relevant reviewed skills into the
  system prompt.

## 6. Coding-agent instruction files (AGENTS.md, Copilot, Claude)

- **What the category does:** Static, hand-written instruction files read at
  agent startup.
- **Overlap:** lessonweaver exports fragments suitable for these files.
- **No overlap:** lessonweaver does not own or auto-write these files; a human
  reviews each fragment before committing it.
- **Together:** See the [coding-agent cookbook](cookbook/coding-agents.md).
- **Example:** A reviewed lesson becomes a Copilot instruction fragment that a
  maintainer pastes into `.github/copilot-instructions.md`.

## 7. Internal runbooks and review checklists

- **What the category does:** Human-maintained process docs and checklists.
- **Overlap:** Both encode operational know-how.
- **No overlap:** Runbooks are written from memory; lessonweaver derives guidance
  from concrete trace evidence and tracks its lifecycle.
- **Together:** Promote a recurring, evidence-backed lesson into the team runbook.
- **Example:** "Validate before publish" graduates from a one-off correction to
  a reviewed checklist item with a linked trace.

## The bottom line

lessonweaver **complements** observability and evals; it does not replace them.
It is the reviewed-guidance layer that sits between *seeing* failures and
*preventing* them.
