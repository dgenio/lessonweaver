# Reviewed deployed-agent improvement artifact

Generated from trace `deployed-refund-policy-stale-001` after human review.
This artifact is framework-neutral; adapters can inject the prompt lesson into
OpenAI Agents SDK instructions, a LlamaIndex system prompt, or a LangGraph node
state after rollout approval.

## Prompt lesson

When answering refund-policy questions, retrieve the current policy version
before quoting eligibility windows. If the current policy cannot be retrieved or
the retrieved sources disagree, state the limitation and escalate to support
operations instead of answering from memory.

## Applies when

- The deployed agent answers refund, cancellation, or eligibility questions.
- The answer depends on policy version, effective date, or jurisdiction.

## Does not apply when

- The user asks for a general explanation that does not require current policy.
- A human support representative has already supplied the current policy text in
  the same interaction.

## Eval gate

- Regression case: "Can I get a refund after 45 days?"
- Expected behavior: retrieves policy version `2026-06` or newer before final
  answer.
- Failure condition: quotes an eligibility window from memory or from policy
  version `2026-04`.

## Rollout metadata

- Reviewer: `support-qa`
- Target framework: `llamaindex`
- Target agent: `customer-support-agent`
- First environment: `staging`
- Canary: 5% of refund-policy questions after eval pass
- Success metric: lower stale-policy eval failure rate over 50 graded sessions
- Rollback trigger: any high-confidence stale-policy answer in canary
- Re-review date: 2026-07-15

## Non-goal

This artifact does not automatically update the deployed agent. It must pass the
eval gate and rollout review before it is loaded into production context.
